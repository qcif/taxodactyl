import groovy.json.JsonSlurper
import groovy.json.JsonOutput
import com.opencsv.CSVReader
import org.yaml.snakeyaml.Yaml
import javax.imageio.ImageIO
import java.security.MessageDigest
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Core contracts. Both diagnostics and promotable observations originate here. */
class CoreAssertions {
    File root
    File destination
    Closure resolve
    Map expectations
    Map evidence
    List<Closure> checks = []
    Set rowKeys = new HashSet()
    Map fixtures = [:]
    Map files = [:]
    Map candidates = [:]
    Map hitSequences = [:]
    Map treeSequences = [:]
    Map metadata = [:]
    Map parameters = [:]
    int maxCandidates = -1
    static final CHANNELS = [H:'ch_hits_for_report', C:'ch_candidates_for_report',
        S:'ch_source_diversity_for_report', T:'ch_homology_trees',
        D:'ch_db_coverage_json', F:'ch_db_coverage_flags', M:'ch_db_coverage_maps']

    static String digest(File file) {
        file.exists() ? MessageDigest.getInstance('SHA-256').digest(file.bytes).encodeHex().toString() : null
    }
    static String ownershipDigest(File root) {
        def hash = MessageDigest.getInstance('SHA-256')
        def fixtures = new File(root,'test/selenium/expected').listFiles()?.findAll { it.name.endsWith('.yaml') } ?: []
        fixtures.sort { it.name }.each { f -> hash.update(f.name.getBytes('UTF-8'));hash.update(f.bytes) }
        hash.digest().encodeHex().toString()
    }
    static Object json(File file) { new JsonSlurper().parse(file) }
    static List csv(File file) {
        new CSVReader(new StringReader(file.text)).withCloseable { reader ->
            def lines = reader.readAll().collect { it.toList() }
            assert lines : "Empty CSV: ${file.name}"
            def header = lines.remove(0)
            assert header.size() == header.unique(false).size() : 'Duplicate CSV columns'
            [header, lines.collect { row ->
                assert row.size() == header.size() : "Wrong CSV row width in ${file.name}"
                [header, row].transpose().collectEntries()
            }]
        }
    }
    static Map fasta(File file) {
        def result = [:]; String id = null
        file.eachLine { line ->
            if (line.startsWith('>')) {
                id = line.substring(1).tokenize()[0]
                assert !result.containsKey(id) : "Duplicate FASTA identifier ${id}"
                result[id] = ''
            } else if (line.trim()) {
                assert id != null : 'Sequence without FASTA header'
                assert line.trim() ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/ : "Invalid sequence ${id}"
                result[id] += line.trim().toUpperCase()
            }
        }
        assert result.values().every { it } : 'Empty FASTA record'
        result
    }
    static List flag(File file, String id) {
        def rows = json(file)
        assert rows instanceof List : 'Flag must be a JSON list'
        rows.each { row ->
            assert row instanceof Map && row.keySet().containsAll(['flag_id','value','target','target_type'])
            def allowed = ['1':['A','B','C','D','E'], '2':['A','B','NA'], '7':['A','B','NA'],
                           '4':['A','B'], '5.1':['A','B','C','NA','ERR'],
                           '5.2':['A','B','C','NA','ERR'], '5.3':['A','B','C','NA','ERR']]
            assert row.flag_id == id && row.value in allowed[id]
        }
        def keys = rows.collect { [it.flag_id,it.target_type,it.target] }
        assert keys.unique(false).size() == keys.size() : 'Duplicate flag record'
        rows
    }
    static void png(File file) {
        def image = ImageIO.read(file)
        assert image != null && image.width > 0 && image.height > 0 : 'Unreadable/empty PNG'
    }
    File file(Object path) { resolve(path.toString()) as File }
    File artifact(String sample, String channel, String name) {
        def found = files[channel]?.get(sample)?.findAll { it.name == name }
        assert found != null && found.size() == 1 : "${sample}/${channel}: expected one ${name}"
        assert found[0].isFile() : "Missing emitted file: ${found[0]}"
        found[0]
    }
    List paths(String sample, String channel) {
        (files[channel]?.get(sample) ?: []).collect { it.toString() }
    }
    void check(String sample, String id, String field, List paths, Closure body) {
        checks << {
            def row = [sample:sample,id:id,field:field,expected:'contract invariant',observed:null,
                       status:'passed',promotable:false,owner:'core',artifacts:paths]
            assert rowKeys.add([sample,id]) : "Ambiguous assertion key: ${sample}/${id}"
            evidence.rows << row
            try { body.call(); row.observed = 'satisfied' }
            catch (AssertionError e) { row.status='failed'; row.diagnostic=e.message; throw e }
            catch (Exception e) {
                row.status='error'; row.diagnostic=id == 'ch_params_json' ? 'Invalid parameters JSON or required settings' : "${e.class.simpleName}: ${e.message}"
                evidence.run.complete=false
                assert false : "${sample}/${id}: ${row.diagnostic}"
            }
        }
    }
    void data(String sample, String id, String field, String kind, Object observed, List paths, String owner=null) {
        assert rowKeys.add([sample,id]) : "Ambiguous assertion key: ${sample}/${id}"
        def expected = expectations.entries?.get(sample)?.get(id)
        def row = [sample:sample,id:id,field:field,kind:kind,observed:observed,
                   expected:expected?.value, owner:owner ?: 'core',promotable:owner == null,
                   status: owner ? 'delegated' : expected == null ? 'unbaselined' : expected.value == observed ? 'passed' : 'failed', artifacts:paths]
        evidence.rows << row
        // Added during evaluation; the returned closure list is drained by the caller.
        if (!owner) checks << { assert row.status == 'passed' : "${sample}/${id} ${field}: expected ${row.expected}, observed ${observed} (${row.status})" }
    }
    String owned(String sample, String component, String field, String role=null, String taxon=null) {
        def fixture = fixtures[sample]
        def comp = fixture?.data?.components?.find { it.id == component }
        def rows = role ? comp?.get(role) : [comp]
        def matches = []
        (rows ?: []).eachWithIndex { row, index ->
            def assertions = row?.assertions ?: []
            def title = assertions.find { it.id == 'title' }?.value
            if (role && !(title instanceof List && title.size() == 1 && title[0].toString() == 'Database coverage of ' + ['candidate':'Candidate','toi':'Taxon of Interest','pmi':'Preliminary Morphology ID'][role] + ' ' + taxon)) return
            def value = assertions.find { it.id == field }?.value
            boolean populated = value instanceof List ? value.any { it != null && it.toString().trim() } : value != null && value.toString().trim()
            if (populated) matches << "${fixture.path}#${component}.${role ?: ''}[${index}].${field}"
        }
        assert matches.size() <= 1 : "Ambiguous Selenium ownership: ${sample}/${role}/${taxon}/${field}"
        matches ? matches[0] : null
    }
    CoreAssertions(File root, File destination, Map run, Closure resolve = { new File(it) }) {
        this.root=root; this.destination=destination; this.resolve=resolve
        File baseline = new File(root,'test/core/expectations.json')
        expectations = baseline.exists() ? json(baseline) as Map : [entries:[:]]
        evidence = [schema_version:1,run:run + [complete:true,evaluated_at:java.time.Instant.now().toString()],
                    expectations_sha256:digest(baseline),ownership_sha256:ownershipDigest(root),contract_sha256:digest(new File(root,'test/core/CoreAssertions.groovy')),rows:[]]
    }
    List<Closure> evaluate() {
        def outcomes = []
        int index = 0
        try {
            while (index < checks.size()) {
                def check = checks[index++]
                try { check.call(); outcomes << { assert true } }
                catch (AssertionError failure) { def captured=failure; outcomes << { throw captured } }
                catch (Exception failure) {
                    evidence.run.complete=false
                    def captured=failure; outcomes << { throw captured }
                }
            }
        } finally { flush() }
        outcomes
    }
    void flush() {
        destination.parentFile.mkdirs()
        def base = destination.parentFile.toPath().toAbsolutePath()
        evidence.rows.each { row -> row.artifacts = row.artifacts.collect { p ->
            def path = new File(p).toPath().toAbsolutePath()
            path.startsWith(base) ? base.relativize(path).toString() : p
        } }
        destination.text = JsonOutput.prettyPrint(JsonOutput.toJson(evidence)) + '\n'
    }
    void prepare(Map channels, boolean success) {
        check('_run','workflow.success','workflow',[]) { assert success : 'Workflow execution failed' }
        check('_run','inputs','metadata',[]) {
            def parsed = csv(new File(root,'test/core/metadata.csv'))
            parsed[1].eachWithIndex { row, index ->
                assert row.sample_id && !metadata.values().any { it.sample_id == row.sample_id }
                metadata[String.format('query_%03d_%s',index+1,row.sample_id)] = row
            }
            new File(root,'test/selenium/expected').eachFileMatch(~/.*\.yaml/) { f ->
                def fixture = new Yaml().load(f.text)
                assert !fixtures.containsKey(fixture.sample_id) : 'Duplicate Selenium fixture'
                fixtures[fixture.sample_id] = [data:fixture,path:'test/selenium/expected/'+f.name]
            }
            evidence.run.metadata_sha256 = digest(new File(root,'test/core/metadata.csv'))
        }
        CHANNELS.each { shortName, name ->
            files[shortName] = [:]
            check('_run',"${shortName}.routing", name,[]) {
                assert channels[name] instanceof List : "Missing channel ${name}"
                def keys = []
                channels[name].each { tuple ->
                    assert tuple instanceof List && tuple.size() == 2 && tuple[0] instanceof String : "Invalid tuple in ${name}"
                    keys << tuple[0]
                    def values = tuple[1] instanceof List ? tuple[1] : [tuple[1]]
                    def resolved = values.collect { file(it) }
                    if (shortName in ['H','C','S','D','F','M']) {
                        assert resolved.every { it.parentFile.name == tuple[0] } : "Wrong sample association: ${name}/${tuple[0]}"
                    }
                    assert resolved*.name.unique(false).size() == resolved.size() : "Duplicate filenames: ${tuple[0]}/${name}"
                    files[shortName][tuple[0]] = resolved
                }
                assert keys.unique(false).size() == keys.size() : "Duplicate samples: ${name}: ${keys}"
                if (shortName != 'M') assert keys.sort() == metadata.keySet().sort() : "${name}: expected ${metadata.keySet()}, observed ${keys}"
                else assert metadata.keySet().containsAll(keys) : "Unexpected map samples ${keys}"
            }
        }
        ['ch_collated_versions','ch_params_json','ch_workflow_timestamp'].each { name ->
            check('_run',name,name,[]) {
                assert channels[name] instanceof List && channels[name].size() == 1
                File f = file(channels[name][0]); assert f.isFile()
                if (name == 'ch_params_json') {
                    parameters = json(f) as Map
                    evidence.run.params_sha256 = digest(f)
                    evidence.run.references = ['blastdb','taxdb'].collectEntries { key ->
                        [key, parameters[key] == null ? 'unavailable' : new File(parameters[key].toString()).name]
                    }
                    def limit = parameters.max_candidates_for_analysis
                    def database = parameters.db_type
                    assert limit instanceof Number && limit > 0
                    assert database == 'blast_core_nt'
                    maxCandidates = limit.toInteger()
                } else if (name == 'ch_workflow_timestamp') {
                    LocalDateTime.parse(f.text.trim(), DateTimeFormatter.ofPattern('yyyyMMdd HHmmss'))
                    evidence.run.workflow_timestamp = f.text.trim()
                } else {
                    evidence.run.versions_sha256 = digest(f)
                    def versions = new Yaml().load(f.text)
                    assert versions instanceof Map && !versions.isEmpty()
                    assert ['blast','mafft','fastme'].every { tool -> f.text.toLowerCase().contains(tool) }
                }
            }
        }
        check('_run','reports.routing','ch_html_report',[]) {
            assert channels.ch_html_report instanceof List
            def keys = channels.ch_html_report.collect { p ->
                def f = file(p); def sample = f.parentFile.name
                assert metadata.containsKey(sample) : "Unexpected report sample ${sample}"
                assert f.name.startsWith('report_'+metadata[sample].sample_id+'_') : "Misassociated report ${f.name}"
                sample
            }
            assert keys.unique(false).size() == keys.size() : 'Duplicate HTML output'
            // Per-sample report presence is owned by unchanged Selenium.
        }
        // Sample checks are scheduled after routing/metadata prerequisites execute.
        checks << { metadata.each { sample, input -> sampleChecks(sample,input) } }
    }
    void sampleChecks(String sample, Map input) {
        String sid = input.sample_id
        check(sid,'H.files','H',paths(sample,'H')) {
            assert files.H[sample]*.name.sort() == ['all_hits.fasta','all_hits.json','query_title.txt']
            assert artifact(sample,'H','query_title.txt').text.trim() == sid
            def hits = json(artifact(sample,'H','all_hits.json'))
            assert hits instanceof Map && hits.hits instanceof List && hits.query_title == sid && hits.query_length instanceof Number
            hits.hits.each { h ->
                assert h.keySet().containsAll(['accession','hit_id','hit_subject','identity','hsps','alignment_length','query_coverage','bitscore','e_value'])
                assert h.accession && h.hsps instanceof List && h.hsps && h.identity instanceof Number && h.identity >= 0 && h.identity <= 1
            }
            assert hits.hits*.accession.unique(false).size() == hits.hits.size()
            def seq = fasta(artifact(sample,'H','all_hits.fasta')); hitSequences[sample]=seq
            assert seq.keySet().sort() == hits.hits*.accession.sort()
            data(sid,'H.membership','H/all_hits.json/accession','membership',seq.keySet().sort(),paths(sample,'H'))
            // Last subject HSP is the documented P1 contract (including gaps).
            hits.hits.each { h ->
                def alignment = h.hsps[-1].alignment
                assert alignment instanceof String
                def subject = alignment.readLines().findAll { it.startsWith('Sbjct') }.collect { line ->
                    line.trim().tokenize().findAll { it ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/ }.join('')
                }.join('').toUpperCase()
                data(sid,'H.sequence/'+h.accession,'H/all_hits.fasta/'+h.accession,'sequence',seq[h.accession],paths(sample,'H'))
                assert seq[h.accession] == subject : "${h.accession}: FASTA differs from last subject HSP"
            }
        }
        ['all_hits.fasta','all_hits.json','query_title.txt'].each { name ->
            check(sid,"C.copy.${name}",'C/'+name,paths(sample,'C')) {
                assert artifact(sample,'C',name).bytes == artifact(sample,'H',name).bytes : "Copied ${name} changed"
            }
        }
        check(sid,'C.content','C/candidates',paths(sample,'C')) {
            def c = json(artifact(sample,'C','candidates.json')); candidates[sample]=c
            assert c instanceof Map && c.hits instanceof List && c.species instanceof List && c.hit_counts instanceof Map
            assert c.species.every { it.species && it.accession && it.hit_count instanceof Number }
            assert c.species*.species.unique(false).size() == c.species.size()
            def count = artifact(sample,'C','candidates_count.txt').text.trim()
            assert count ==~ /\d+/
            assert count.toInteger() == c.species.size()
            def table = csv(artifact(sample,'C','candidates.csv'))
            assert table[0] == ['species','taxid','accession','hit_subject','identity','query_coverage','alignment_length','e_value','bitscore']
            assert table[1]*.accession.unique(false).size() == table[1].size()
            assert table[1]*.accession.sort() == c.hits*.accession.sort()
            assert table[1]*.species.unique().sort() == c.species*.species.sort()
            def seq = fasta(artifact(sample,'C','candidates.fasta'))
            assert seq.keySet().sort() == c.hits*.accession.sort()
            assert hitSequences.containsKey(sample) : 'Missing validated H FASTA prerequisite'
            seq.each { id, sequence -> assert sequence == hitSequences[sample][id] : "Candidate sequence ${id} changed" }
            def phylo = fasta(artifact(sample,'C','candidates_phylogeny.fasta')); treeSequences[sample]=phylo
            phylo.each { id, sequence -> assert sequence == hitSequences[sample][id] : "Phylogeny sequence ${id} not in hits" }
            data(sid,'C.phylogeny.membership','C/candidates_phylogeny.fasta','membership',phylo.keySet().sort(),paths(sample,'C'))
            assert maxCandidates > 0 : 'Missing validated parameters prerequisite'
            boolean plot = c.species.size() > maxCandidates
            def names = files.C[sample]*.name
            assert names.contains('candidates_identity_boxplot.png') == plot
            if (plot) png(artifact(sample,'C','candidates_identity_boxplot.png'))
            def allowed = ['1.flag','2.flag','7.flag','all_hits.fasta','all_hits.json','query_title.txt',
                'candidates.csv','candidates.json','candidates.fasta','candidates_count.txt','candidates_phylogeny.fasta',
                'assigned_taxonomy.csv','preliminary_id_match.csv','taxa_of_concern_detected.csv','candidates_identity_boxplot.png']
            assert allowed.containsAll(names) : "Uninventoried candidate files: ${names - allowed}"
            def f1 = flag(artifact(sample,'C','1.flag'),'1')
            assert names.contains('assigned_taxonomy.csv') == (f1[0].value == 'A')
            if (names.contains('assigned_taxonomy.csv')) {
                def assigned = csv(artifact(sample,'C','assigned_taxonomy.csv'))
                assert assigned[0] == table[0] && assigned[1] == table[1]
            }
        }
        ['1':'conclusion_flag','2':'toi_flag','7':'preliminary_flag'].each { id, field ->
            check(sid,"C.flag.${id}",'C/'+id+'.flag',paths(sample,'C')) {
                def rows = flag(artifact(sample,'C',id+'.flag'),id)
                assert rows.size() == 1 && rows[0].target == null && rows[0].target_type == null
                data(sid,"C.flag.${id}.value",'C/'+id+'.flag/value','flag',rows[0].value,paths(sample,'C'),owned(sid,'overview_tab',field))
            }
        }
        check(sid,'C.toi','C/taxa_of_concern_detected.csv',paths(sample,'C')) {
            def expected = input.taxa_of_interest.tokenize('|')*.trim()
            def present = files.C[sample]*.name.contains('taxa_of_concern_detected.csv')
            assert present == !expected.isEmpty()
            if (present) {
                def table = csv(artifact(sample,'C','taxa_of_concern_detected.csv'))
                assert table[0] == ['Taxon of interest','Match rank','Match taxon','Match species','Match accession','Match identity']
                assert table[1]*.get('Taxon of interest') == expected
                assert candidates[sample] != null : 'Missing candidate prerequisite'
                table[1].each { row ->
                    if (row['Match accession']) assert candidates[sample].hits*.accession.contains(row['Match accession'])
                }
            }
        }
        check(sid,'C.pmi','C/preliminary_id_match.csv',paths(sample,'C')) {
            def rows = flag(artifact(sample,'C','7.flag'),'7')
            boolean present = files.C[sample]*.name.contains('preliminary_id_match.csv')
            assert present == (rows[0].value == 'A')
            if (present) {
                def table = csv(artifact(sample,'C','preliminary_id_match.csv'))
                assert table[0] == ['rank','taxon'] && table[1].size() == 1 : 'Malformed preliminary-ID CSV'
                assert table[1][0].taxon.equalsIgnoreCase(input.preliminary_id.trim())
            }
        }
        check(sid,'S.routing-content','S',paths(sample,'S')) {
            assert candidates.containsKey(sample) && maxCandidates > 0 : 'Missing C/params prerequisite'
            def c = candidates[sample]
            boolean assessed = c.species.size() in 1..maxCandidates
            assert files.S.containsKey(sample)
            assert files.S[sample]*.name.sort() == (assessed ? ['4.flag','aggregated_sources.json'] : [])
            if (assessed) {
                def sources = json(artifact(sample,'S','aggregated_sources.json'))
                assert sources instanceof Map && sources.keySet().sort() == c.species*.species.sort()
                def flags = flag(artifact(sample,'S','4.flag'),'4')
                assert flags*.target.sort() == sources.keySet().sort()
                sources.each { taxon, groups ->
                    assert groups instanceof List && groups.every { it instanceof List }
                    def accessions = groups.flatten()*.accession
                    assert c.hits*.accession.containsAll(accessions) : 'Source accession outside candidates'
                    data(sid,'S.membership/'+taxon,'S/aggregated_sources.json/'+taxon,'membership',accessions.unique(false).sort(),paths(sample,'S'))
                    groups.flatten().each { source -> assert source.accession && source.publications instanceof List && source.is_automated instanceof Boolean }
                }
                flags.each { f -> data(sid,'S.flag/'+f.target,'S/4.flag/'+f.target,'flag',f.value,paths(sample,'S')) }
            }
        }
        check(sid,'T.labels','T/candidates_phylogeny.nwk',paths(sample,'T')) {
            assert files.T[sample]?.size() == 1
            def tree = artifact(sample,'T','candidates_phylogeny.nwk').text.trim()
            assert treeSequences.containsKey(sample) : 'Missing validated phylogeny FASTA prerequisite'
            def selected = treeSequences[sample].keySet()
            if (selected.isEmpty()) assert !tree : 'Expected deliberately empty tree'
            else {
                def labels = new CoreNewick(tree).leaves()
                assert labels.sort() == (selected.toList()+['QUERY']).sort() : 'Tree leaves differ from selected FASTA + QUERY'
            }
        }
        coverageChecks(sample,input)
    }
    void coverageChecks(String sample, Map input) {
        def sid = input.sample_id
        check(sid,'D.content','D/db_coverage.json',paths(sample,'D')) {
            assert files.D[sample]?.size() == 1
            def d = json(artifact(sample,'D','db_coverage.json'))
            assert d.coverage instanceof Map && d.coverage.keySet().sort() == ['candidate','pmi','toi']
            d.coverage.each { role, taxa ->
                assert taxa instanceof Map
                data(sid,"D.membership/${role}","D/coverage/${role}",'membership',taxa.keySet().sort(),paths(sample,'D'))
                taxa.each { taxon, values ->
                    assert values instanceof Map && values.keySet().containsAll(['target','related','country'])
                    assert values.target == null || values.target instanceof Number && values.target >= 0 && values.target == values.target.toInteger()
                    data(sid,"D.state/${role}/${taxon}/target","D/coverage/${role}/${taxon}/target-state",'state',values.containsKey('not_assessed') ? 'not_assessed' : values.target == null ? 'null' : 'assessed',paths(sample,'D'))
                    data(sid,"D.count/${role}/${taxon}/target","D/coverage/${role}/${taxon}/target",'count',values.target,paths(sample,'D'),owned(sid,'database_coverage','record_count',role,taxon))
                    ['related','country'].each { field ->
                        def counts = values[field]
                        assert counts == null || counts instanceof Map || field == 'country' && counts == 'NA'
                        if (counts instanceof Map) {
                            data(sid,"D.membership/${role}/${taxon}/${field}","D/coverage/${role}/${taxon}/${field}",'membership',counts.keySet().sort(),paths(sample,'D'))
                            counts.each { species, count ->
                                assert count == null || count instanceof Number && count >= 0 && count == count.toInteger()
                                String owner = null
                                if (field == 'related') {
                                    // Only the fixture's explicitly named first bar is delegated.
                                    def fixture = fixtures[sid]?.data?.components?.find { it.id == 'database_coverage' }
                                    def row = fixture?.get(role)?.find { r -> r.assertions.find { it.id == 'title' }?.value == [('Database coverage of '+['candidate':'Candidate','toi':'Taxon of Interest','pmi':'Preliminary Morphology ID'][role]+' '+taxon).toString()] }
                                    def first = row?.assertions?.find { it.id == 'first_bar_species' }?.value
                                    if (first == [species]) owner=owned(sid,'database_coverage','first_bar_count',role,taxon)
                                }
                                data(sid,"D.count/${role}/${taxon}/${field}/${species}","D/coverage/${role}/${taxon}/${field}/${species}",'count',count,paths(sample,'D'),owner)
                            }
                        } else data(sid,"D.state/${role}/${taxon}/${field}","D/coverage/${role}/${taxon}/${field}",'state',counts == null ? 'null' : 'NA',paths(sample,'D'))
                    }
                }
            }
        }
        ['5.1','5.2','5.3'].each { id ->
            check(sid,"F.${id}.records",'F/'+id+'.flag',paths(sample,'F')) {
                assert files.F[sample]*.name.sort() == ['5.1.flag','5.2.flag','5.3.flag']
                def rows = flag(artifact(sample,'F',id+'.flag'),id)
                rows.each { f -> assert f.target && f.target_type in ['candidate','toi','pmi'] }
                def d = json(artifact(sample,'D','db_coverage.json')).coverage
                def required = d.collectMany { role, taxa -> taxa.keySet().collect { role+'/'+it } }.sort()
                assert rows.collect { it.target_type+'/'+it.target }.sort() == required : 'Flag record membership differs from coverage targets'
                rows.each { f ->
                    def owner = id == '5.3' ? null : owned(sid,'database_coverage',id == '5.1' ? 'flag_text1':'flag_text2',f.target_type,f.target)
                    data(sid,"F.value/${id}/${f.target_type}/${f.target}","F/${id}/${f.target_type}/${f.target}",'flag',f.value,paths(sample,'F'),owner)
                }
            }
        }
        check(sid,'M.files','M/maps',paths(sample,'M')) {
            def maps = files.M[sample] ?: []
            data(sid,'M.membership','M/map filenames','membership',maps*.name.sort(),paths(sample,'M'))
            maps.each { f -> assert f.name ==~ /map.*\.png/; png(f) }
        }
    }
}

/** Small recursive Newick reader: validates grammar, branch lengths and duplicate leaves. */
class CoreNewick {
    String text; int pos=0; List labels=[]
    CoreNewick(String text) { this.text=text }
    void space() { while (pos<text.size() && Character.isWhitespace(text.charAt(pos))) pos++ }
    String label() {
        space(); int start=pos
        if (pos<text.size() && text[pos]=="'") {
            pos++; def value=''
            while (pos<text.size()) {
                if (text[pos]=="'") { pos++; if (pos<text.size() && text[pos]=="'") { value+="'";pos++ } else return value }
                else value+=text[pos++]
            }
            assert false : 'Unterminated Newick label'
        }
        while(pos<text.size() && !(text[pos] in [':',',','(',')',';']) && !Character.isWhitespace(text.charAt(pos))) pos++
        text.substring(start,pos)
    }
    void node() {
        space(); assert pos<text.size()
        if (text[pos]=='(') {
            pos++;node();space();assert text[pos]==',' : 'Internal node requires children'
            while (text[pos]==',') { pos++;node();space() }
            assert text[pos]==')';pos++;label()
        } else { def value=label();assert value;labels<<value }
        space()
        if (pos<text.size() && text[pos]==':') {
            pos++;int start=pos
            while(pos<text.size() && !(text[pos] in [',',')',';'])) pos++
            double length=Double.parseDouble(text.substring(start,pos).trim());assert Double.isFinite(length)
        }
    }
    List leaves() { node();space();assert pos==text.size()-1 && text[pos]==';';assert labels.unique(false).size()==labels.size();labels }
}
