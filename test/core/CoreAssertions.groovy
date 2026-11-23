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
    File expectedDir
    Map expected = [:]          // sample_id -> [file, sha256, entries: key -> [value, type, component, group, name, assertion]]
    Map observedKeys = [:]      // sample_id -> keys of data rows emitted this run
    Map components = [:]        // schema component id -> definition
    Map checkComponent = [:]    // invariant check id -> component id
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
            assert lines : "${file.name} should have a header line; the file is empty"
            def header = lines.remove(0)
            assert header.size() == header.unique(false).size() : "${file.name}: column names should be unique; header is ${header}"
            [header, lines.collect { row ->
                assert row.size() == header.size() : "${file.name}: every row should have ${header.size()} columns like the header; found ${row.size()} in ${row}"
                [header, row].transpose().collectEntries()
            }]
        }
    }
    static Map fasta(File file) {
        def result = [:]; String id = null
        file.eachLine { line ->
            if (line.startsWith('>')) {
                id = line.substring(1).tokenize()[0]
                assert !result.containsKey(id) : "${file.name}: each sequence name should appear once; ${id} appears twice"
                result[id] = ''
            } else if (line.trim()) {
                assert id != null : "${file.name}: sequence data should follow a '>' name line; found sequence before any name"
                assert line.trim() ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/ : "${file.name}: sequence ${id} should contain only nucleotide letters; found '${line.trim().take(60)}'"
                result[id] += line.trim().toUpperCase()
            }
        }
        assert result.values().every { it } : "${file.name}: every sequence should be non-empty; empty: ${result.findAll { !it.value }.keySet()}"
        result
    }
    static List flag(File file, String id) {
        def rows = json(file)
        assert rows instanceof List : 'Flag must be a JSON list'
        rows.each { row ->
            assert row instanceof Map && row.keySet().containsAll(['flag_id','value','target','target_type']) : "${file.name}: every record needs flag_id, value, target and target_type; found ${brief(row)}"
            def allowed = ['1':['A','B','C','D','E'], '2':['A','B','NA'], '7':['A','B','NA'],
                           '4':['A','B'], '5.1':['A','B','C','NA','ERR'],
                           '5.2':['A','B','C','NA','ERR'], '5.3':['A','B','C','NA','ERR']]
            assert row.flag_id == id : "${file.name}: flag_id should be ${id}; found ${row.flag_id}"
            assert row.value in allowed[id] : "${file.name}: flag ${id} value should be one of ${allowed[id].join('/')}; found ${row.value}"
        }
        def keys = rows.collect { [it.flag_id,it.target_type,it.target] }
        assert keys.unique(false).size() == keys.size() : "${file.name}: each role/target should appear once; found duplicates ${keys.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
        rows
    }
    static void png(File file) {
        def image = ImageIO.read(file)
        assert image != null && image.width > 0 && image.height > 0 : "${file.name} should be a readable, non-empty PNG image; it could not be read as one"
    }
    File file(Object path) { resolve(path.toString()) as File }
    File artifact(String sample, String channel, String name) {
        def found = files[channel]?.get(sample)?.findAll { it.name == name }
        assert found != null && found.size() == 1 : "${name} should be present once in the ${CHANNELS[channel]} output for this sample; found ${found?.size() ?: 0}"
        assert found[0].isFile() : "${name} is listed in the workflow output but the file does not exist: ${found[0]}"
        found[0]
    }
    List paths(String sample, String channel, List names = null) {
        (files[channel]?.get(sample) ?: []).findAll { names == null || it.name in names }.collect { it.toString() }
    }
    static String fingerprint(String sequence) {
        MessageDigest.getInstance('SHA-256').digest(sequence.getBytes('UTF-8')).encodeHex().toString().take(16)
    }
    static String key(String component, String group, String name, String assertion) {
        group ? "${component}/${group}/${name}/${assertion}".toString() : "${component}/${assertion}".toString()
    }
    Map assertionDef(String component, String assertion) {
        def found = components[component]?.assertions?.get(assertion)
        assert found : "Undeclared data value ${component}/${assertion}; declare it in test/core/schema.yaml"
        found as Map
    }
    static boolean valid(String type, Object value) {
        switch (type) {
            case 'membership': return value instanceof List && value.every { it instanceof String && it } && value.unique(false).size() == value.size()
            case 'fingerprints': return value instanceof Map && value.every { k, v -> k instanceof String && k && v instanceof String && v ==~ /[0-9a-f]{16}/ }
            case 'flag': return value in ['A','B','C','D','E','NA','ERR']
            case 'state': return value in ['assessed','not_assessed','null','NA']
            default: return false
        }
    }
    static boolean same(String type, Object expected, Object observed) {
        if (type == 'membership') return expected instanceof List && observed instanceof List && expected.sort(false) == observed.sort(false)
        expected == observed
    }
    static String brief(Object value) {
        def text
        try { text = value instanceof String ? value : JsonOutput.toJson(value) } catch (Exception ignored) { text = String.valueOf(value) }
        text.size() > 200 ? text.take(200) + '…' : text
    }
    void check(String sample, String id, String field, List paths, Closure body) {
        String component = checkComponent[id]
        assert component : "Undeclared check ${id}; declare it in test/core/schema.yaml"
        checks << {
            def row = [sample:sample,id:id,component:component,field:field,rule:components[component].checks[id].rule,
                       observed:null,status:'passed',promotable:false,owner:'core',artifacts:paths]
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
    /** One data value. Stored values come from the sample's expected/*.yaml; others are informational. */
    void data(String sample, String component, String group, String name, String assertion, Object observed, List paths, Map opts = [:]) {
        def definition = assertionDef(component, assertion)
        String id = key(component, group, name, assertion)
        assert rowKeys.add([sample,id]) : "Ambiguous assertion key: ${sample}/${id}"
        observedKeys.computeIfAbsent(sample) { new HashSet() } << id
        String owner = opts.owner
        boolean stored = definition.stored != false
        def entry = expected[sample]?.entries?.get(id)
        String status = owner ? 'delegated' : !stored ? 'not_checked' : entry == null ? 'unbaselined'
            : same(definition.type, entry.value, observed) ? 'passed' : 'failed'
        def row = [sample:sample,id:id,component:component,group:group,name:name,assertion:assertion,
                   field:opts.field ?: id,kind:definition.type,observed:observed,expected:entry?.value,
                   owner:owner ?: 'core',promotable:!owner && stored,status:status,artifacts:paths]
        if (owner && entry != null) {
            // Selenium now owns a value core still stores: the core entry must be removed (promote).
            row += [observed:null,owner:'core',promotable:true,status:'failed',absent:true,
                    diagnostic:"Selenium now owns this value (${owner}); remove the stored core entry."]
        }
        // Full values (e.g. sequences behind fingerprints) are kept only where a reviewer needs them.
        if (opts.detail != null && status != 'passed') row.detail = opts.detail
        evidence.rows << row
        if (row.promotable) checks << { assert row.status == 'passed' : "${sample}/${id}: expected ${brief(entry?.value)}, observed ${brief(row.observed)} (${row.absent ? 'stale' : row.status})" }
    }
    /** Expected entries with no observation this run are failures that promote can remove. */
    void staleEntries() {
        def ids = metadata.values()*.sample_id as Set
        expected.each { sid, file ->
            if (!(sid in ids)) return
            // A broken prerequisite already explains missing observations; do not cascade.
            def blocked = evidence.rows.findAll { it.sample == sid && it.kind == null && it.status in ['failed','error'] }*.component as Set
            file.entries.each { id, entry ->
                if (id in (observedKeys[sid] ?: []) || entry.component in blocked) return
                def row = [sample:sid,id:id,component:entry.component,group:entry.group,name:entry.name,assertion:entry.assertion,
                           field:id,kind:entry.type,observed:null,expected:entry.value,absent:true,owner:'core',
                           promotable:true,status:'failed',artifacts:[],
                           diagnostic:'Expected entry was not observed: the value no longer exists in the outputs, or Selenium now owns it.']
                evidence.rows << row
                checks << { assert false : "${sid}/${id}: expected entry not observed" }
            }
        }
    }
    void loadExpected(Set ids) {
        def problems = []
        def yamlFiles = expectedDir.listFiles()?.findAll { it.isFile() && it.name.endsWith('.yaml') }?.sort { it.name } ?: []
        yamlFiles.each { f ->
            def doc
            try { doc = new Yaml().load(f.text) }
            catch (Exception e) { problems << "${f.name}: invalid YAML (${e.message?.readLines()?.find()})"; return }
            if (!(doc instanceof Map) || !(doc.sample_id instanceof String) || !doc.sample_id) { problems << "${f.name}: missing sample_id"; return }
            String sid = doc.sample_id
            if (expected.containsKey(sid)) { problems << "${f.name}: duplicate sample_id ${sid} (also in ${new File(expected[sid].file).name})"; return }
            if (!(sid in ids)) { problems << "${f.name}: sample_id ${sid} is not in test/core/metadata.csv (orphan file; delete it or add the sample)"; return }
            def entries = [:]
            def add = { String component, String group, String name, Object list ->
                if (!(list instanceof List)) { problems << "${f.name}: ${component}${group ? '/'+group+'/'+name : ''}: assertions must be a list"; return }
                list.each { a ->
                    def definition = a instanceof Map ? components[component].assertions?.get(a.id) : null
                    if (definition == null || definition.stored == false) { problems << "${f.name}: ${component}: unknown or unstorable assertion ${a instanceof Map ? a.id : a}"; return }
                    if (a.type != null && a.type != definition.type) { problems << "${f.name}: ${component}/${a.id}: type ${a.type} should be ${definition.type}"; return }
                    if (!valid(definition.type, a.value)) { problems << "${f.name}: ${component}/${a.id}: invalid ${definition.type} value ${brief(a.value)}"; return }
                    String id = key(component, group, name, a.id)
                    if (entries.containsKey(id)) { problems << "${f.name}: duplicate entry ${id}"; return }
                    entries[id] = [value:a.value,type:definition.type,component:component,group:group,name:name,assertion:a.id]
                }
            }
            if (doc.components != null && !(doc.components instanceof List)) { problems << "${f.name}: components must be a list"; return }
            (doc.components ?: []).each { comp ->
                def definition = comp instanceof Map ? components[comp.id] : null
                if (definition == null || comp.id == 'run') { problems << "${f.name}: unknown component ${comp instanceof Map ? comp.id : comp}"; return }
                comp.each { k, v ->
                    if (k == 'id') return
                    if (k == 'assertions') add(comp.id, null, null, v)
                    else if (k in (definition.groups ?: [])) {
                        if (!(v instanceof List)) { problems << "${f.name}: ${comp.id}/${k} must be a list"; return }
                        v.each { item ->
                            if (item instanceof Map && item.name instanceof String && item.name) add(comp.id, k, item.name, item.assertions)
                            else problems << "${f.name}: ${comp.id}/${k}: entry without name"
                        }
                    } else problems << "${f.name}: ${comp.id}: unknown key ${k}"
                }
            }
            String relative = f.canonicalPath.startsWith(root.canonicalPath + File.separator) ? f.canonicalPath.substring(root.canonicalPath.size() + 1) : f.canonicalPath
            expected[sid] = [file:relative,sha256:digest(f),entries:entries]
        }
        evidence.expectations = ids.collectEntries { sid -> [(sid): expected[sid] ? [file:expected[sid].file,sha256:expected[sid].sha256] : null] }
        assert !problems : problems.join('\n')
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
        expectedDir = new File(System.getenv('CORE_EXPECTED_DIR') ?: new File(root,'test/core/expected').path)
        File schemaFile = new File(root,'test/core/schema.yaml')
        def schema = new Yaml().load(schemaFile.text)
        assert schema?.schema_version == 2 : 'Unsupported test/core/schema.yaml'
        schema.components.each { c ->
            components[c.id] = c
            (c.checks ?: [:]).each { id, definition -> assert !checkComponent.containsKey(id) : "Duplicate check ${id}"; checkComponent[id] = c.id }
        }
        evidence = [schema_version:2,run:run + [complete:true,evaluated_at:java.time.Instant.now().toString()],
                    expectations:[:],ownership_sha256:ownershipDigest(root),schema_sha256:digest(schemaFile),
                    contract_sha256:digest(new File(root,'test/core/CoreAssertions.groovy')),rows:[]]
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
        check('_run','workflow.success','workflow',[]) { assert success : 'The workflow run should finish successfully; it failed (see nf-test output and .command.err files)' }
        check('_run','inputs','metadata',[]) {
            def parsed = csv(new File(root,'test/core/metadata.csv'))
            parsed[1].eachWithIndex { row, index ->
                assert row.sample_id : "metadata.csv row ${index + 2} should have a sample_id; it is empty"
                assert !metadata.values().any { it.sample_id == row.sample_id } : "metadata.csv: sample_id ${row.sample_id} should be unique; it appears more than once"
                metadata[String.format('query_%03d_%s',index+1,row.sample_id)] = row
            }
            new File(root,'test/selenium/expected').eachFileMatch(~/.*\.yaml/) { f ->
                def fixture = new Yaml().load(f.text)
                assert !fixtures.containsKey(fixture.sample_id) : "test/selenium/expected: sample_id ${fixture.sample_id} should have one fixture; ${f.name} duplicates it"
                fixtures[fixture.sample_id] = [data:fixture,path:'test/selenium/expected/'+f.name]
            }
            evidence.run.metadata_sha256 = digest(new File(root,'test/core/metadata.csv'))
            evidence.run.samples = metadata.values()*.sample_id
        }
        check('_run','expected.files','test/core/expected',[]) { loadExpected(metadata.values()*.sample_id as Set) }
        CHANNELS.each { shortName, name ->
            files[shortName] = [:]
            check('_run',"${shortName}.routing", name,[]) {
                assert channels[name] instanceof List : "The workflow should emit channel ${name}; it was not emitted"
                def keys = []
                channels[name].each { tuple ->
                    assert tuple instanceof List && tuple.size() == 2 && tuple[0] instanceof String : "${name} items should be [sample, files]; found ${brief(tuple)}"
                    keys << tuple[0]
                    def values = tuple[1] instanceof List ? tuple[1] : [tuple[1]]
                    def resolved = values.collect { file(it) }
                    if (shortName in ['H','C','S','D','F','M']) {
                        assert resolved.every { it.parentFile.name == tuple[0] } : "${name}: files for ${tuple[0]} should be in that sample's folder; found ${resolved.findAll { it.parentFile.name != tuple[0] }*.parentFile*.name.unique()}"
                    }
                    assert resolved*.name.unique(false).size() == resolved.size() : "${name}: each file name should appear once for ${tuple[0]}; duplicates ${resolved*.name.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
                    files[shortName][tuple[0]] = resolved
                }
                assert keys.unique(false).size() == keys.size() : "${name} should have one entry per sample; repeated: ${keys.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
                if (shortName != 'M') assert keys.sort() == metadata.keySet().sort() : "${name} should have one entry for every sample in metadata.csv; missing ${metadata.keySet() - keys}, unexpected ${keys - metadata.keySet()}"
                else assert metadata.keySet().containsAll(keys) : "${name} should only contain samples from metadata.csv; unexpected ${keys - metadata.keySet()}"
            }
        }
        ['ch_collated_versions','ch_params_json','ch_workflow_timestamp'].each { name ->
            check('_run',name,name,[]) {
                assert channels[name] instanceof List && channels[name].size() == 1 : "${name} should emit exactly one file; found ${channels[name] instanceof List ? channels[name].size() : 'nothing'}"
                File f = file(channels[name][0]); assert f.isFile() : "${name}: emitted file does not exist: ${f}"
                if (name == 'ch_params_json') {
                    parameters = json(f) as Map
                    evidence.run.params_sha256 = digest(f)
                    evidence.run.references = ['blastdb','taxdb'].collectEntries { key ->
                        [key, parameters[key] == null ? 'unavailable' : new File(parameters[key].toString()).name]
                    }
                    def limit = parameters.max_candidates_for_analysis
                    def database = parameters.db_type
                    assert limit instanceof Number && limit > 0 : "Parameter max_candidates_for_analysis should be a positive number; found ${limit}"
                    assert database == 'blast_core_nt' : "Parameter db_type should be blast_core_nt for the core test; found ${database}"
                    maxCandidates = limit.toInteger()
                } else if (name == 'ch_workflow_timestamp') {
                    try { LocalDateTime.parse(f.text.trim(), DateTimeFormatter.ofPattern('yyyyMMdd HHmmss')) }
                    catch (Exception e) { assert false : "Workflow timestamp should look like 20261123 043225; found '${f.text.trim().take(40)}'" }
                    evidence.run.workflow_timestamp = f.text.trim()
                } else {
                    evidence.run.versions_sha256 = digest(f)
                    def versions = new Yaml().load(f.text)
                    assert versions instanceof Map && !versions.isEmpty() : "Software versions file should be a non-empty YAML map; found ${brief(versions)}"
                    assert ['blast','mafft','fastme'].every { tool -> f.text.toLowerCase().contains(tool) } : "Software versions should list blast, mafft and fastme; missing ${['blast','mafft','fastme'].findAll { !f.text.toLowerCase().contains(it) }}"
                }
            }
        }
        check('_run','reports.routing','ch_html_report',[]) {
            assert channels.ch_html_report instanceof List : 'The workflow should emit channel ch_html_report; it was not emitted'
            def keys = channels.ch_html_report.collect { p ->
                def f = file(p); def sample = f.parentFile.name
                assert metadata.containsKey(sample) : "HTML report ${f.name} is in folder ${sample}, which is not a sample in metadata.csv"
                assert f.name.startsWith('report_'+metadata[sample].sample_id+'_') : "HTML report in ${sample} should be named report_${metadata[sample].sample_id}_…; found ${f.name}"
                sample
            }
            assert keys.unique(false).size() == keys.size() : "Each sample should have one HTML report; repeated: ${keys.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
            // Per-sample report presence is owned by unchanged Selenium.
        }
        // Sample checks are scheduled after routing/metadata prerequisites execute.
        checks << {
            metadata.each { sample, input -> sampleChecks(sample,input) }
            checks << { staleEntries() }
        }
    }
    void sampleChecks(String sample, Map input) {
        String sid = input.sample_id
        check(sid,'H.files','H',paths(sample,'H')) {
            assert files.H[sample]*.name.sort() == ['all_hits.fasta','all_hits.json','query_title.txt'] : "Hits output should be exactly all_hits.fasta, all_hits.json and query_title.txt; found ${files.H[sample]*.name.sort()}"
            def title = artifact(sample,'H','query_title.txt').text.trim()
            assert title == sid : "query_title.txt should contain the sample ID ${sid}; found '${title.take(80)}' (outputs may belong to another sample)"
            def hits = json(artifact(sample,'H','all_hits.json'))
            assert hits instanceof Map && hits.hits instanceof List && hits.query_length instanceof Number : 'all_hits.json should contain query_title, query_length and a hits list'
            assert hits.query_title == sid : "all_hits.json query_title should be ${sid}; found ${hits.query_title}"
            hits.hits.each { h ->
                def required = ['accession','hit_id','hit_subject','identity','hsps','alignment_length','query_coverage','bitscore','e_value']
                assert h.keySet().containsAll(required) : "all_hits.json: hit ${h.accession ?: '?'} is missing ${required - h.keySet()}"
                assert h.accession && h.hsps instanceof List && h.hsps : "all_hits.json: every hit needs an accession and at least one HSP; hit ${h.accession ?: '?'} does not"
                assert h.identity instanceof Number && h.identity >= 0 && h.identity <= 1 : "all_hits.json: identity should be between 0 and 1; hit ${h.accession} has ${h.identity}"
            }
            assert hits.hits*.accession.unique(false).size() == hits.hits.size() : "all_hits.json: each accession should appear once; repeated ${hits.hits*.accession.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
            def seq = fasta(artifact(sample,'H','all_hits.fasta')); hitSequences[sample]=seq
            assert seq.keySet().sort() == hits.hits*.accession.sort() : "all_hits.fasta and all_hits.json should list the same accessions; only in FASTA ${seq.keySet() - hits.hits*.accession}, only in JSON ${hits.hits*.accession - seq.keySet()}"
            data(sid,'blast_hits',null,null,'accessions',seq.keySet().sort(),paths(sample,'H',['all_hits.json','all_hits.fasta']),[field:'H/all_hits.json/accession'])
            data(sid,'blast_hits',null,null,'sequence_fingerprints',seq.collectEntries { id, sequence -> [id, fingerprint(sequence)] }.sort(),
                 paths(sample,'H',['all_hits.fasta']),[field:'H/all_hits.fasta',detail:seq])
            // Last subject HSP is the documented P1 contract (including gaps).
            hits.hits.each { h ->
                def alignment = h.hsps[-1].alignment
                assert alignment instanceof String : "all_hits.json: hit ${h.accession} should have alignment text in its last HSP"
                def subject = alignment.readLines().findAll { it.startsWith('Sbjct') }.collect { line ->
                    line.trim().tokenize().findAll { it ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/ }.join('')
                }.join('').toUpperCase()
                assert seq[h.accession] == subject : "all_hits.fasta sequence for ${h.accession} should equal the subject line of its last HSP in all_hits.json; they differ (FASTA length ${seq[h.accession]?.size()}, HSP length ${subject.size()})"
            }
        }
        ['all_hits.fasta','all_hits.json','query_title.txt'].each { name ->
            check(sid,"C.copy.${name}",'C/'+name,paths(sample,'C',[name])+paths(sample,'H',[name])) {
                assert artifact(sample,'C',name).bytes == artifact(sample,'H',name).bytes : "The copy of ${name} in the candidate folder should be identical to the hits output; it differs"
            }
        }
        check(sid,'C.content','C/candidates',paths(sample,'C',['candidates.json','candidates_count.txt','candidates.csv','candidates.fasta',
                'candidates_phylogeny.fasta','assigned_taxonomy.csv','candidates_identity_boxplot.png','1.flag'])) {
            def c = json(artifact(sample,'C','candidates.json')); candidates[sample]=c
            assert c instanceof Map && c.hits instanceof List && c.species instanceof List && c.hit_counts instanceof Map : 'candidates.json should contain hits, species and hit_counts'
            assert c.species.every { it.species && it.accession && it.hit_count instanceof Number } : "candidates.json: every species entry needs species, accession and hit_count; incomplete: ${c.species.findAll { !(it.species && it.accession && it.hit_count instanceof Number) }*.species}"
            assert c.species*.species.unique(false).size() == c.species.size() : "candidates.json: each species should appear once; repeated ${c.species*.species.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
            def count = artifact(sample,'C','candidates_count.txt').text.trim()
            assert count ==~ /\d+/ : "candidates_count.txt should contain a whole number; found '${count.take(40)}'"
            assert count.toInteger() == c.species.size() : "candidates_count.txt says ${count} but candidates.json lists ${c.species.size()} species"
            def table = csv(artifact(sample,'C','candidates.csv'))
            def columns = ['species','taxid','accession','hit_subject','identity','query_coverage','alignment_length','e_value','bitscore']
            assert table[0] == columns : "candidates.csv header should be ${columns.join(',')}; found ${table[0].join(',')}"
            assert table[1]*.accession.unique(false).size() == table[1].size() : "candidates.csv: each accession should appear once; repeated ${table[1]*.accession.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
            assert table[1]*.accession.sort() == c.hits*.accession.sort() : "candidates.csv and candidates.json should list the same hits; only in CSV ${table[1]*.accession - c.hits*.accession}, only in JSON ${c.hits*.accession - table[1]*.accession}"
            assert table[1]*.species.unique().sort() == c.species*.species.sort() : "candidates.csv and candidates.json should list the same species; only in CSV ${table[1]*.species.unique() - c.species*.species}, only in JSON ${c.species*.species - table[1]*.species}"
            def seq = fasta(artifact(sample,'C','candidates.fasta'))
            assert seq.keySet().sort() == c.hits*.accession.sort() : "candidates.fasta and candidates.json should list the same hits; only in FASTA ${seq.keySet() - c.hits*.accession}, only in JSON ${c.hits*.accession - seq.keySet()}"
            assert hitSequences.containsKey(sample) : 'Cannot compare with BLAST hits: the hits check for this sample failed first (see Hit files)'
            seq.each { id, sequence -> assert sequence == hitSequences[sample][id] : "candidates.fasta sequence ${id} should equal the same hit in all_hits.fasta; it differs" }
            def phylo = fasta(artifact(sample,'C','candidates_phylogeny.fasta')); treeSequences[sample]=phylo
            phylo.each { id, sequence -> assert sequence == hitSequences[sample][id] : "candidates_phylogeny.fasta sequence ${id} should be one of the BLAST hits, unchanged; it is not" }
            data(sid,'phylogeny',null,null,'selected_sequences',phylo.keySet().sort(),paths(sample,'C',['candidates_phylogeny.fasta']),[field:'C/candidates_phylogeny.fasta'])
            assert maxCandidates > 0 : 'Cannot apply the candidate limit: the parameters file check failed first'
            boolean plot = c.species.size() > maxCandidates
            def names = files.C[sample]*.name
            assert names.contains('candidates_identity_boxplot.png') == plot : "candidates_identity_boxplot.png should ${plot ? '' : 'not '}exist with ${c.species.size()} candidate species (limit ${maxCandidates}); it ${names.contains('candidates_identity_boxplot.png') ? 'exists' : 'is missing'}"
            if (plot) png(artifact(sample,'C','candidates_identity_boxplot.png'))
            def allowed = ['1.flag','2.flag','7.flag','all_hits.fasta','all_hits.json','query_title.txt',
                'candidates.csv','candidates.json','candidates.fasta','candidates_count.txt','candidates_phylogeny.fasta',
                'assigned_taxonomy.csv','preliminary_id_match.csv','taxa_of_concern_detected.csv','candidates_identity_boxplot.png']
            assert allowed.containsAll(names) : "Candidate folder contains files this test does not know about: ${names - allowed} (add them to the test if intended)"
            def f1 = flag(artifact(sample,'C','1.flag'),'1')
            assert names.contains('assigned_taxonomy.csv') == (f1[0].value == 'A') : "assigned_taxonomy.csv should exist only when flag 1 is A; flag 1 is ${f1[0].value} and the file ${names.contains('assigned_taxonomy.csv') ? 'exists' : 'is missing'}"
            if (names.contains('assigned_taxonomy.csv')) {
                def assigned = csv(artifact(sample,'C','assigned_taxonomy.csv'))
                assert assigned[0] == table[0] && assigned[1] == table[1] : 'assigned_taxonomy.csv should have the same header and rows as candidates.csv; it differs'
            }
        }
        ['1':'conclusion_flag','2':'toi_flag','7':'preliminary_flag'].each { id, field ->
            check(sid,"C.flag.${id}",'C/'+id+'.flag',paths(sample,'C',[id+'.flag'])) {
                def rows = flag(artifact(sample,'C',id+'.flag'),id)
                assert rows.size() == 1 : "${id}.flag should contain exactly one record; found ${rows.size()}"
                assert rows[0].target == null && rows[0].target_type == null : "${id}.flag should have no target; found ${rows[0].target_type}/${rows[0].target}"
                data(sid,'candidates',null,null,'flag_'+id,rows[0].value,paths(sample,'C',[id+'.flag']),
                     [field:'C/'+id+'.flag/value',owner:owned(sid,'overview_tab',field)])
            }
        }
        check(sid,'C.toi','C/taxa_of_concern_detected.csv',paths(sample,'C',['taxa_of_concern_detected.csv'])) {
            def expected = input.taxa_of_interest.tokenize('|')*.trim()
            def present = files.C[sample]*.name.contains('taxa_of_concern_detected.csv')
            assert present == !expected.isEmpty() : "taxa_of_concern_detected.csv should ${expected ? '' : 'not '}exist because the input lists ${expected ? expected.size() + ' taxa of interest' : 'no taxa of interest'}; it ${present ? 'exists' : 'is missing'}"
            if (present) {
                def table = csv(artifact(sample,'C','taxa_of_concern_detected.csv'))
                def columns = ['Taxon of interest','Match rank','Match taxon','Match species','Match accession','Match identity']
                assert table[0] == columns : "taxa_of_concern_detected.csv header should be ${columns.join(',')}; found ${table[0].join(',')}"
                assert table[1]*.get('Taxon of interest') == expected : "taxa_of_concern_detected.csv should have one row per input taxon of interest, in order ${expected}; found ${table[1]*.get('Taxon of interest')}"
                assert candidates[sample] != null : 'Cannot check match accessions: the candidate files check failed first'
                table[1].each { row ->
                    if (row['Match accession']) assert candidates[sample].hits*.accession.contains(row['Match accession']) : "taxa_of_concern_detected.csv: match accession ${row['Match accession']} should be one of the candidate hits; it is not"
                }
            }
        }
        check(sid,'C.pmi','C/preliminary_id_match.csv',paths(sample,'C',['preliminary_id_match.csv','7.flag'])) {
            def rows = flag(artifact(sample,'C','7.flag'),'7')
            boolean present = files.C[sample]*.name.contains('preliminary_id_match.csv')
            assert present == (rows[0].value == 'A') : "preliminary_id_match.csv should exist only when flag 7 is A; flag 7 is ${rows[0].value} and the file ${present ? 'exists' : 'is missing'}"
            if (present) {
                def text = artifact(sample,'C','preliminary_id_match.csv').text
                def lines = text.readLines().findAll { it.trim() }
                assert lines.size() == 2 && lines[0] == 'rank,taxon' : "preliminary_id_match.csv should be a header line 'rank,taxon' and one data line (e.g. 'genus,${input.preliminary_id.trim()}'); found ${lines.size()} line(s): ${lines.collect { "'" + it.take(80) + "'" }.join(' / ')}" + (lines.size() == 1 && lines[0].startsWith('rank,taxon') ? ' (header and data joined: missing line break)' : '')
                def table = csv(artifact(sample,'C','preliminary_id_match.csv'))
                assert table[1][0].taxon.equalsIgnoreCase(input.preliminary_id.trim()) : "preliminary_id_match.csv should name the input preliminary ID '${input.preliminary_id.trim()}'; found '${table[1][0].taxon}'"
            }
        }
        check(sid,'S.routing-content','S',paths(sample,'S')) {
            assert candidates.containsKey(sample) && maxCandidates > 0 : 'Cannot decide whether sources should be assessed: the candidate files or parameters check failed first'
            def c = candidates[sample]
            boolean assessed = c.species.size() in 1..maxCandidates
            assert files.S.containsKey(sample) : 'Source-diversity output is missing for this sample'
            assert files.S[sample]*.name.sort() == (assessed ? ['4.flag','aggregated_sources.json'] : []) : "With ${c.species.size()} candidate species (assessed for 1..${maxCandidates}), source-diversity output should be ${assessed ? '4.flag and aggregated_sources.json' : 'empty (not assessed)'}; found ${files.S[sample]*.name.sort() ?: 'nothing'}"
            if (assessed) {
                def sources = json(artifact(sample,'S','aggregated_sources.json'))
                assert sources instanceof Map && sources.keySet().sort() == c.species*.species.sort() : "aggregated_sources.json should have one entry per candidate species ${c.species*.species.sort()}; found ${sources instanceof Map ? sources.keySet().sort() : brief(sources)}"
                def flags = flag(artifact(sample,'S','4.flag'),'4')
                assert flags*.target.sort() == sources.keySet().sort() : "4.flag should have one record per candidate species ${sources.keySet().sort()}; found ${flags*.target.sort()}"
                sources.each { taxon, groups ->
                    assert groups instanceof List && groups.every { it instanceof List } : "aggregated_sources.json: ${taxon} should be a list of source groups"
                    def accessions = groups.flatten()*.accession
                    assert c.hits*.accession.containsAll(accessions) : "aggregated_sources.json: ${taxon} lists accessions that are not candidate hits: ${accessions - c.hits*.accession}"
                    data(sid,'source_diversity','candidates',taxon,'source_accessions',accessions.unique(false).sort(),
                         paths(sample,'S',['aggregated_sources.json']),[field:'S/aggregated_sources.json/'+taxon])
                    groups.flatten().each { source -> assert source.accession && source.publications instanceof List && source.is_automated instanceof Boolean : "aggregated_sources.json: every source of ${taxon} needs accession, publications and is_automated; found ${brief(source)}" }
                }
                flags.each { f -> data(sid,'source_diversity','candidates',f.target,'flag_4',f.value,paths(sample,'S',['4.flag']),[field:'S/4.flag/'+f.target]) }
            }
        }
        check(sid,'T.labels','T/candidates_phylogeny.nwk',paths(sample,'T')) {
            assert files.T[sample]?.size() == 1 : "Tree output should be one candidates_phylogeny.nwk file; found ${files.T[sample]?.size() ?: 0}"
            def tree = artifact(sample,'T','candidates_phylogeny.nwk').text.trim()
            assert treeSequences.containsKey(sample) : 'Cannot compare tree leaves: the candidate files check failed first'
            def selected = treeSequences[sample].keySet()
            if (selected.isEmpty()) assert !tree : 'No sequences were selected for the tree, so candidates_phylogeny.nwk should be empty; it is not'
            else {
                def labels = new CoreNewick(tree).leaves()
                assert labels.sort() == (selected.toList()+['QUERY']).sort() : "Tree leaves should be the selected sequences plus QUERY; missing from tree ${(selected.toList()+['QUERY']) - labels}, unexpected ${labels - selected.toList() - ['QUERY']}"
            }
        }
        coverageChecks(sample,input)
    }
    void coverageChecks(String sample, Map input) {
        def sid = input.sample_id
        check(sid,'D.content','D/db_coverage.json',paths(sample,'D',['db_coverage.json'])) {
            assert files.D[sample]?.size() == 1 : "Coverage output should be one db_coverage.json; found ${files.D[sample]?.size() ?: 0}"
            def d = json(artifact(sample,'D','db_coverage.json'))
            assert d.coverage instanceof Map && d.coverage.keySet().sort() == ['candidate','pmi','toi'] : "db_coverage.json should have coverage sections candidate, pmi and toi; found ${d.coverage instanceof Map ? d.coverage.keySet().sort() : brief(d.coverage)}"
            def where = paths(sample,'D',['db_coverage.json'])
            d.coverage.each { role, taxa ->
                assert taxa instanceof Map : "db_coverage.json: ${role} should map taxa to results; found ${brief(taxa)}"
                data(sid,'database_coverage',null,null,role+'_taxa',taxa.keySet().sort(),where,[field:"D/coverage/${role}"])
                taxa.each { taxon, values ->
                    assert values instanceof Map && values.keySet().containsAll(['target','related','country']) : "db_coverage.json: ${role}/${taxon} should have target, related and country; found ${values instanceof Map ? values.keySet() : brief(values)}"
                    assert values.target == null || values.target instanceof Number && values.target >= 0 && values.target == values.target.toInteger() : "db_coverage.json: ${role}/${taxon} target count should be a whole number or null; found ${values.target}"
                    data(sid,'database_coverage',role,taxon,'target_state',values.containsKey('not_assessed') ? 'not_assessed' : values.target == null ? 'null' : 'assessed',
                         where,[field:"D/coverage/${role}/${taxon}/target"])
                    // Record counts are live GenBank/BOLD numbers: Selenium owns them (±10%); core only reports them.
                    data(sid,'database_coverage',role,taxon,'target_record_count',values.target,where,
                         [field:"D/coverage/${role}/${taxon}/target",owner:owned(sid,'database_coverage','record_count',role,taxon)])
                    ['related','country'].each { field ->
                        def counts = values[field]
                        assert counts == null || counts instanceof Map || field == 'country' && counts == 'NA' : "db_coverage.json: ${role}/${taxon}/${field} should be a species list${field == 'country' ? ', NA' : ''} or null; found ${brief(counts)}"
                        if (counts instanceof Map) {
                            counts.each { species, count -> assert count == null || count instanceof Number && count >= 0 && count == count.toInteger() : "db_coverage.json: ${role}/${taxon}/${field}/${species} count should be a whole number or null; found ${count}" }
                            // Species names must match; per-species counts are deliberately not compared (user decision 2026-11-23).
                            data(sid,'database_coverage',role,taxon,field+'_species',counts.keySet().sort(),where,[field:"D/coverage/${role}/${taxon}/${field}"])
                        } else data(sid,'database_coverage',role,taxon,field+'_state',counts == null ? 'null' : 'NA',where,[field:"D/coverage/${role}/${taxon}/${field}"])
                    }
                }
            }
        }
        ['5.1','5.2','5.3'].each { id ->
            check(sid,"F.${id}.records",'F/'+id+'.flag',paths(sample,'F',[id+'.flag'])+paths(sample,'D',['db_coverage.json'])) {
                assert files.F[sample]*.name.sort() == ['5.1.flag','5.2.flag','5.3.flag'] : "Coverage flags should be 5.1.flag, 5.2.flag and 5.3.flag; found ${files.F[sample]*.name.sort()}"
                def rows = flag(artifact(sample,'F',id+'.flag'),id)
                rows.each { f -> assert f.target && f.target_type in ['candidate','toi','pmi'] : "${id}.flag: every record needs a target and a target_type of candidate/toi/pmi; found ${f.target_type}/${f.target}" }
                def d = json(artifact(sample,'D','db_coverage.json')).coverage
                def required = d.collectMany { role, taxa -> taxa.keySet().collect { role+'/'+it } }.sort()
                def found = rows.collect { it.target_type+'/'+it.target }.sort()
                assert found == required : "${id}.flag should have one record per taxon in db_coverage.json; missing ${required - found}, unexpected ${found - required}"
                rows.each { f ->
                    def owner = id == '5.3' ? null : owned(sid,'database_coverage',id == '5.1' ? 'flag_text1':'flag_text2',f.target_type,f.target)
                    data(sid,'coverage_flags',f.target_type,f.target,'flag_'+id.replace('.','_'),f.value,paths(sample,'F',[id+'.flag']),
                         [field:"F/${id}/${f.target_type}/${f.target}",owner:owner])
                }
            }
        }
        check(sid,'M.files','M/maps',paths(sample,'M')) {
            def maps = files.M[sample] ?: []
            data(sid,'maps',null,null,'filenames',maps*.name.sort(),paths(sample,'M'),[field:'M/map filenames'])
            maps.each { f ->
                assert f.name ==~ /map.*\.png/ : "Coverage map files should be named map*.png; found ${f.name}"
                assert f.isFile() : "${f.name} is listed in the workflow output but the file does not exist (if the run was copied, the copy may have lost it)"
                png(f)
            }
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
        space(); assert pos<text.size() : 'candidates_phylogeny.nwk ends unexpectedly (incomplete tree)'
        if (text[pos]=='(') {
            pos++;node();space();assert text[pos]==',' : 'candidates_phylogeny.nwk: every bracketed group needs at least two members'
            while (text[pos]==',') { pos++;node();space() }
            assert text[pos]==')' : 'candidates_phylogeny.nwk: unbalanced brackets';pos++;label()
        } else { def value=label();assert value : 'candidates_phylogeny.nwk: a leaf has no name';labels<<value }
        space()
        if (pos<text.size() && text[pos]==':') {
            pos++;int start=pos
            while(pos<text.size() && !(text[pos] in [',',')',';'])) pos++
            double length=Double.parseDouble(text.substring(start,pos).trim());assert Double.isFinite(length) : 'candidates_phylogeny.nwk: branch length is not a finite number'
        }
    }
    List leaves() {
        node();space()
        assert pos==text.size()-1 && text[pos]==';' : 'candidates_phylogeny.nwk should end with a single ;'
        assert labels.unique(false).size()==labels.size() : "candidates_phylogeny.nwk: each leaf name should appear once; repeated ${labels.countBy { it }.findAll { k, v -> v > 1 }.keySet()}"
        labels
    }
}
