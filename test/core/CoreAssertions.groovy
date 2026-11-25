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
    static final FLAG_VALUES = ['1':['A','B','C','D','E'], '2':['A','B','NA'], '7':['A','B','NA'],
                                '4':['A','B'], '5.1':['A','B','C','NA','ERR'],
                                '5.2':['A','B','C','NA','ERR'], '5.3':['A','B','C','NA','ERR']]

    // ------------------------------------------------------------------ messages
    // Every failure reads "<where>: <rule>\nExpected: <value>\nActual: <value>".
    // Values are printed as they are (strings quoted, line breaks as ⏎); no diagnosis.

    static Desc d(Object text) { new Desc(text: String.valueOf(text)) }
    static String show(Object value) {
        if (value instanceof Desc) return value.text
        def text
        try {
            text = value instanceof String ? '"' + value.replace('\r', '').replace('\n', '⏎') + '"'
                 : value instanceof Collection || value instanceof Map ? JsonOutput.toJson(value)
                 : String.valueOf(value)
        } catch (Exception ignored) { text = String.valueOf(value) }
        text.size() > 200 ? text.take(200) + '…' : text
    }
    static String msg(Object where, String rule, Object expected, Object actual, String difference = null) {
        "${where}: ${rule}\nExpected: ${show(expected)}\nActual: ${show(actual)}" + (difference ? "\nDifference: ${difference}" : '')
    }
    static void holds(boolean ok, Object where, String rule, Object expected, Object actual, String difference = null) {
        assert ok : msg(where, rule, expected, actual, difference)
    }
    static void same(Object where, String rule, Object expected, Object actual) {
        holds(expected == actual, where, rule, expected, actual)
    }
    static void sameSet(Object where, String rule, Collection expected, Collection actual) {
        def e = expected.toList().sort(false), a = actual.toList().sort(false)
        holds(e == a, where, rule, e, a, "missing ${show(e - a)}; unexpected ${show(a - e)}")
    }
    static void unique(Object where, String rule, Collection values) {
        def repeated = values.countBy { it }.findAll { k, v -> v > 1 }.keySet().toList()
        holds(!repeated, where, rule, d('no repeats'), d("repeated ${show(repeated)}"))
    }
    static void present(Object where, String rule, boolean shouldExist, boolean exists) {
        holds(shouldExist == exists, where, rule, d(shouldExist ? 'file present' : 'no file'), d(exists ? 'file present' : 'no file'))
    }
    static Desc count(int n, String noun) { d("${n} ${noun}${n == 1 ? '' : 's'}") }

    // ------------------------------------------------------------------- readers

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
            holds(!lines.isEmpty(), file.name, 'has a header line', d('header line'), d('empty file'))
            def header = lines.remove(0)
            unique(file.name, 'column names are unique', header)
            [header, lines.collect { row ->
                same(file.name, 'every row has as many columns as the header', count(header.size(), 'column'), count(row.size(), 'column'))
                [header, row].transpose().collectEntries()
            }]
        }
    }
    static Map fasta(File file) {
        def result = [:]; String id = null
        file.eachLine { line ->
            if (line.startsWith('>')) {
                id = line.substring(1).tokenize()[0]
                holds(!result.containsKey(id), file.name, 'each sequence name appears once', d('no repeats'), d("repeated ${show(id)}"))
                result[id] = ''
            } else if (line.trim()) {
                holds(id != null, file.name, "sequence lines follow a '>' name line", d('name line first'), line.trim())
                holds(line.trim() ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/, file.name, "sequence ${id} contains only nucleotide letters",
                      d('nucleotide letters'), line.trim())
                result[id] += line.trim().toUpperCase()
            }
        }
        def empty = result.findAll { !it.value }.keySet().toList()
        holds(!empty, file.name, 'every sequence is non-empty', d('no empty sequences'), d("empty ${show(empty)}"))
        result
    }
    /** Reads a flag file: JSON list of records with the right flag_id, no repeated role/target. Values are checked by flagValue(). */
    static List flag(File file, String id) {
        def rows = json(file)
        holds(rows instanceof List, file.name, 'is a JSON list of records', d('list'), rows)
        rows.each { row ->
            holds(row instanceof Map && row.keySet().containsAll(['flag_id','value','target','target_type']), file.name,
                  'every record has flag_id, value, target and target_type', d('all four fields'), row)
            same(file.name, 'flag_id', id, row.flag_id)
        }
        unique(file.name, 'each role/target appears once', rows.collect { [it.target_type, it.target] })
        rows
    }
    static void flagValue(File file, String id, Map row) {
        holds(row.value in FLAG_VALUES[id], file.name, "flag ${id} value${row.target ? ' for ' + row.target_type + '/' + row.target : ''}",
              d('one of ' + FLAG_VALUES[id].join('/')), row.value)
    }
    static void png(File file) {
        def image = ImageIO.read(file)
        holds(image != null && image.width > 0 && image.height > 0, file.name, 'is a readable PNG image', d('readable image'), d('unreadable or empty'))
    }
    File file(Object path) { resolve(path.toString()) as File }
    File artifact(String sample, String channel, String name) {
        def found = files[channel]?.get(sample)?.findAll { it.name == name }
        same(name, "listed once in ${CHANNELS[channel]}", count(1, 'file'), count(found?.size() ?: 0, 'file'))
        holds(found[0].isFile(), name, 'listed output file exists', d('file present'), d("missing: ${found[0]}"))
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
        holds(found != null, 'test/core/schema.yaml', 'data value is declared', d("${component}/${assertion} declared"), d('not declared'))
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
    static boolean equalValue(String type, Object expected, Object observed) {
        if (type == 'membership') return expected instanceof List && observed instanceof List && expected.sort(false) == observed.sort(false)
        expected == observed
    }
    static String brief(Object value) { show(value) }

    // -------------------------------------------------------- checks and values

    void check(String sample, String id, String field, List paths, Closure body) {
        String component = checkComponent[id]
        holds(component != null, 'test/core/schema.yaml', 'check is declared', d("${id} declared"), d('not declared'))
        checks << {
            def row = [sample:sample,id:id,component:component,field:field,rule:components[component].checks[id].rule,
                       observed:null,status:'passed',promotable:false,owner:'core',artifacts:paths]
            holds(rowKeys.add([sample,id]), "${sample}/${id}", 'check runs once', d('once'), d('twice'))
            evidence.rows << row
            try { body.call(); row.observed = 'satisfied' }
            catch (AssertionError e) { row.status='failed'; row.diagnostic=e.message; throw e }
            catch (Exception e) {
                row.status='error'
                row.diagnostic=msg("${sample}/${id}", 'check could be evaluated', d('no error'),
                                   d(id == 'ch_params_json' ? 'invalid parameters JSON or required settings' : "${e.class.simpleName}: ${e.message}"))
                evidence.run.complete=false
                assert false : row.diagnostic
            }
        }
    }
    /** One data value. Stored values come from the sample's expected/*.yaml; others are informational. */
    void data(String sample, String component, String group, String name, String assertion, Object observed, List paths, Map opts = [:]) {
        def definition = assertionDef(component, assertion)
        String id = key(component, group, name, assertion)
        holds(rowKeys.add([sample,id]), "${sample}/${id}", 'value recorded once', d('once'), d('twice'))
        observedKeys.computeIfAbsent(sample) { new HashSet() } << id
        String owner = opts.owner
        boolean stored = definition.stored != false
        def entry = expected[sample]?.entries?.get(id)
        String status = owner ? 'delegated' : !stored ? 'not_checked' : entry == null ? 'unbaselined'
            : equalValue(definition.type, entry.value, observed) ? 'passed' : 'failed'
        def row = [sample:sample,id:id,component:component,group:group,name:name,assertion:assertion,
                   field:opts.field ?: id,kind:definition.type,observed:observed,expected:entry?.value,
                   owner:owner ?: 'core',promotable:!owner && stored,status:status,artifacts:paths]
        if (owner && entry != null) {
            // Selenium now owns a value core still stores: the core entry must be removed (promote).
            row += [observed:null,owner:'core',promotable:true,status:'failed',absent:true,
                    diagnostic:msg("${sample}/${id}", 'stored core value', entry.value, d("now checked by Selenium (${owner})"))]
        }
        // Full values (e.g. sequences behind fingerprints) are kept only where a reviewer needs them.
        if (opts.detail != null && status != 'passed') row.detail = opts.detail
        evidence.rows << row
        if (row.promotable) checks << {
            holds(row.status == 'passed', "${sample}/${id}", 'stored value', entry == null ? d('no stored value') : entry.value,
                  row.absent ? d('not produced') : row.observed)
        }
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
                def message = msg("${sid}/${id}", 'stored value', entry.value, d('not produced'))
                def row = [sample:sid,id:id,component:entry.component,group:entry.group,name:entry.name,assertion:entry.assertion,
                           field:id,kind:entry.type,observed:null,expected:entry.value,absent:true,owner:'core',
                           promotable:true,status:'failed',artifacts:[],diagnostic:message]
                evidence.rows << row
                checks << { assert false : message }
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
            if (!(sid in ids)) { problems << "${f.name}: sample_id ${sid} is not in test/core/metadata.csv (orphan file)"; return }
            def entries = [:]
            def add = { String component, String group, String name, Object list ->
                if (!(list instanceof List)) { problems << "${f.name}: ${component}${group ? '/'+group+'/'+name : ''}: assertions must be a list"; return }
                list.each { a ->
                    def definition = a instanceof Map ? components[component].assertions?.get(a.id) : null
                    if (definition == null || definition.stored == false) { problems << "${f.name}: ${component}: unknown or unstorable assertion ${a instanceof Map ? a.id : a}"; return }
                    if (a.type != null && a.type != definition.type) { problems << "${f.name}: ${component}/${a.id}: type ${a.type} should be ${definition.type}"; return }
                    if (!valid(definition.type, a.value)) { problems << "${f.name}: ${component}/${a.id}: invalid ${definition.type} value ${show(a.value)}"; return }
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
        holds(!problems, 'test/core/expected', 'valid per-sample expectation files', d('no problems'), d(problems.join('; ')))
    }
    /** Selenium fixture field that checks this value (populated expectation), or null. */
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
        holds(matches.size() <= 1, "${sample}/${role}/${taxon}/${field}", 'at most one Selenium fixture field', count(1, 'field'), count(matches.size(), 'field'))
        matches ? matches[0] : null
    }
    CoreAssertions(File root, File destination, Map run, Closure resolve = { new File(it) }) {
        this.root=root; this.destination=destination; this.resolve=resolve
        expectedDir = new File(System.getenv('CORE_EXPECTED_DIR') ?: new File(root,'test/core/expected').path)
        File schemaFile = new File(root,'test/core/schema.yaml')
        def schema = new Yaml().load(schemaFile.text)
        same('test/core/schema.yaml', 'schema_version', 2, schema?.schema_version)
        schema.components.each { c ->
            components[c.id] = c
            (c.checks ?: [:]).each { id, definition ->
                holds(!checkComponent.containsKey(id), 'test/core/schema.yaml', 'check IDs are unique', d('unique'), d("repeated ${id}"))
                checkComponent[id] = c.id
            }
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

    // ------------------------------------------------------------- run checks

    void prepare(Map channels, boolean success) {
        check('_run','workflow.success','workflow',[]) {
            holds(success, 'workflow', 'run finished successfully', d('success'), d('failed (see nf-test output and .command.err files)'))
        }
        check('_run','inputs','metadata',[]) {
            def parsed = csv(new File(root,'test/core/metadata.csv'))
            parsed[1].eachWithIndex { row, index ->
                holds(row.sample_id as boolean, 'metadata.csv', "row ${index + 2} has a sample_id", d('sample_id'), row.sample_id)
                holds(!metadata.values().any { it.sample_id == row.sample_id }, 'metadata.csv', 'sample_id is unique', d('unique'), d("repeated ${show(row.sample_id)}"))
                metadata[String.format('query_%03d_%s',index+1,row.sample_id)] = row
            }
            new File(root,'test/selenium/expected').eachFileMatch(~/.*\.yaml/) { f ->
                def fixture = new Yaml().load(f.text)
                holds(!fixtures.containsKey(fixture.sample_id), 'test/selenium/expected', 'one fixture per sample_id', d('one'), d("${f.name} repeats ${fixture.sample_id}"))
                fixtures[fixture.sample_id] = [data:fixture,path:'test/selenium/expected/'+f.name]
            }
            evidence.run.metadata_sha256 = digest(new File(root,'test/core/metadata.csv'))
            evidence.run.samples = metadata.values()*.sample_id
        }
        check('_run','expected.files','test/core/expected',[]) { loadExpected(metadata.values()*.sample_id as Set) }
        CHANNELS.each { shortName, name ->
            files[shortName] = [:]
            check('_run',"${shortName}.routing", name,[]) {
                holds(channels[name] instanceof List, name, 'channel is emitted', d('emitted'), d('not emitted'))
                def keys = []
                channels[name].each { tuple ->
                    holds(tuple instanceof List && tuple.size() == 2 && tuple[0] instanceof String, name, 'items are [sample, files]', d('[sample, files]'), tuple)
                    keys << tuple[0]
                    def values = tuple[1] instanceof List ? tuple[1] : [tuple[1]]
                    def resolved = values.collect { file(it) }
                    if (shortName in ['H','C','S','D','F','M']) {
                        def folders = resolved*.parentFile*.name.unique()
                        holds(folders.every { it == tuple[0] }, name, "files of ${tuple[0]} are in its folder", [tuple[0]], folders)
                    }
                    unique(name, "file names of ${tuple[0]} are unique", resolved*.name)
                    files[shortName][tuple[0]] = resolved
                }
                unique(name, 'one entry per sample', keys)
                if (shortName != 'M') sameSet(name, 'one entry for every sample in metadata.csv', metadata.keySet(), keys)
                else holds(metadata.keySet().containsAll(keys), name, 'only samples from metadata.csv', d('samples from metadata.csv'), keys - metadata.keySet())
            }
        }
        ['ch_collated_versions','ch_params_json','ch_workflow_timestamp'].each { name ->
            check('_run',name,name,[]) {
                same(name, 'emits one file', count(1, 'file'), count(channels[name] instanceof List ? channels[name].size() : 0, 'file'))
                File f = file(channels[name][0])
                holds(f.isFile(), name, 'emitted file exists', d('file present'), d("missing: ${f}"))
                if (name == 'ch_params_json') {
                    parameters = json(f) as Map
                    evidence.run.params_sha256 = digest(f)
                    evidence.run.references = ['blastdb','taxdb'].collectEntries { key ->
                        [key, parameters[key] == null ? 'unavailable' : new File(parameters[key].toString()).name]
                    }
                    def limit = parameters.max_candidates_for_analysis
                    holds(limit instanceof Number && limit > 0, 'parameters', 'max_candidates_for_analysis', d('a positive number'), limit)
                    same('parameters', 'db_type', 'blast_core_nt', parameters.db_type)
                    maxCandidates = limit.toInteger()
                } else if (name == 'ch_workflow_timestamp') {
                    boolean parsed = true
                    try { LocalDateTime.parse(f.text.trim(), DateTimeFormatter.ofPattern('yyyyMMdd HHmmss')) } catch (Exception e) { parsed = false }
                    holds(parsed, f.name, 'timestamp format', d('yyyyMMdd HHmmss, e.g. 20261123 043225'), f.text.trim().take(40))
                    evidence.run.workflow_timestamp = f.text.trim()
                } else {
                    evidence.run.versions_sha256 = digest(f)
                    def versions = new Yaml().load(f.text)
                    holds(versions instanceof Map && !versions.isEmpty(), f.name, 'is a non-empty YAML map', d('YAML map'), versions)
                    def listed = ['blast','mafft','fastme'].findAll { f.text.toLowerCase().contains(it) }
                    sameSet(f.name, 'lists blast, mafft and fastme', ['blast','mafft','fastme'], listed)
                }
            }
        }
        check('_run','reports.routing','ch_html_report',[]) {
            holds(channels.ch_html_report instanceof List, 'ch_html_report', 'channel is emitted', d('emitted'), d('not emitted'))
            def keys = channels.ch_html_report.collect { p ->
                def f = file(p); def sample = f.parentFile.name
                holds(metadata.containsKey(sample), f.name, 'report folder is a sample in metadata.csv', d('known sample'), sample)
                holds(f.name.startsWith('report_'+metadata[sample].sample_id+'_'), sample, 'HTML report name',
                      d("report_${metadata[sample].sample_id}_…"), f.name)
                sample
            }
            unique('ch_html_report', 'one HTML report per sample', keys)
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
            sameSet('hits output', 'file names', ['all_hits.fasta','all_hits.json','query_title.txt'], files.H[sample]*.name)
            same('query_title.txt', 'sample ID', sid, artifact(sample,'H','query_title.txt').text.trim())
            def hits = json(artifact(sample,'H','all_hits.json'))
            holds(hits instanceof Map && hits.hits instanceof List && hits.query_length instanceof Number, 'all_hits.json',
                  'has query_title, query_length and a hits list', d('all three'), hits instanceof Map ? hits.keySet() : hits)
            same('all_hits.json', 'query_title', sid, hits.query_title)
            def required = ['accession','hit_id','hit_subject','identity','hsps','alignment_length','query_coverage','bitscore','e_value']
            hits.hits.each { h ->
                holds(h.keySet().containsAll(required), 'all_hits.json', "hit ${h.accession ?: '?'} has the required fields", required, h.keySet())
                holds(h.accession && h.hsps instanceof List && h.hsps, 'all_hits.json', "hit ${h.accession ?: '?'} has an accession and HSPs", d('accession and at least one HSP'), d('missing'))
                holds(h.identity instanceof Number && h.identity >= 0 && h.identity <= 1, 'all_hits.json', "identity of ${h.accession}", d('between 0 and 1'), h.identity)
            }
            unique('all_hits.json', 'each accession appears once', hits.hits*.accession)
            def seq = fasta(artifact(sample,'H','all_hits.fasta')); hitSequences[sample]=seq
            sameSet('all_hits.fasta', 'same accessions as all_hits.json', hits.hits*.accession, seq.keySet())
            data(sid,'blast_hits',null,null,'accessions',seq.keySet().sort(),paths(sample,'H',['all_hits.json','all_hits.fasta']),[field:'H/all_hits.json/accession'])
            data(sid,'blast_hits',null,null,'sequence_fingerprints',seq.collectEntries { id, sequence -> [id, fingerprint(sequence)] }.sort(),
                 paths(sample,'H',['all_hits.fasta']),[field:'H/all_hits.fasta',detail:seq])
            // Last subject HSP is the documented P1 contract (including gaps).
            hits.hits.each { h ->
                def alignment = h.hsps[-1].alignment
                holds(alignment instanceof String, 'all_hits.json', "hit ${h.accession} last HSP has alignment text", d('text'), alignment)
                def subject = alignment.readLines().findAll { it.startsWith('Sbjct') }.collect { line ->
                    line.trim().tokenize().findAll { it ==~ /[ACGTURYSWKMBDHVNacgturyswkmbdhvn.\-]+/ }.join('')
                }.join('').toUpperCase()
                same('all_hits.fasta', "sequence ${h.accession} equals the subject of its last HSP in all_hits.json", subject, seq[h.accession])
            }
        }
        ['all_hits.fasta','all_hits.json','query_title.txt'].each { name ->
            check(sid,"C.copy.${name}",'C/'+name,paths(sample,'C',[name])+paths(sample,'H',[name])) {
                def copy = artifact(sample,'C',name), original = artifact(sample,'H',name)
                holds(copy.bytes == original.bytes, "candidates/${name}", 'identical to the hits output', d("${original.size()} bytes, same content"),
                      d("${copy.size()} bytes, different content"))
            }
        }
        check(sid,'C.content','C/candidates',paths(sample,'C',['candidates.json','candidates_count.txt','candidates.csv','candidates.fasta',
                'candidates_phylogeny.fasta','assigned_taxonomy.csv','candidates_identity_boxplot.png','1.flag'])) {
            def c = json(artifact(sample,'C','candidates.json')); candidates[sample]=c
            holds(c instanceof Map && c.hits instanceof List && c.species instanceof List && c.hit_counts instanceof Map, 'candidates.json',
                  'has hits, species and hit_counts', d('all three'), c instanceof Map ? c.keySet() : c)
            def incomplete = c.species.findAll { !(it.species && it.accession && it.hit_count instanceof Number) }
            holds(!incomplete, 'candidates.json', 'every species has species, accession and hit_count', d('all complete'), incomplete)
            unique('candidates.json', 'each species appears once', c.species*.species)
            def count = artifact(sample,'C','candidates_count.txt').text.trim()
            holds(count ==~ /\d+/, 'candidates_count.txt', 'contains a whole number', d('whole number'), count)
            same('candidates_count.txt', 'equals the number of species in candidates.json', c.species.size(), count.toInteger())
            def table = csv(artifact(sample,'C','candidates.csv'))
            same('candidates.csv', 'header', ['species','taxid','accession','hit_subject','identity','query_coverage','alignment_length','e_value','bitscore'], table[0])
            unique('candidates.csv', 'each accession appears once', table[1]*.accession)
            sameSet('candidates.csv', 'same hits as candidates.json', c.hits*.accession, table[1]*.accession)
            sameSet('candidates.csv', 'same species as candidates.json', c.species*.species, table[1]*.species.unique())
            def seq = fasta(artifact(sample,'C','candidates.fasta'))
            sameSet('candidates.fasta', 'same hits as candidates.json', c.hits*.accession, seq.keySet())
            holds(hitSequences.containsKey(sample), 'candidates.fasta', 'compared with all_hits.fasta', d('hit files valid'), d('hit files check failed first'))
            seq.each { id, sequence -> same('candidates.fasta', "sequence ${id} equals all_hits.fasta", hitSequences[sample][id], sequence) }
            def phylo = fasta(artifact(sample,'C','candidates_phylogeny.fasta')); treeSequences[sample]=phylo
            phylo.each { id, sequence -> same('candidates_phylogeny.fasta', "sequence ${id} equals all_hits.fasta", hitSequences[sample][id], sequence) }
            data(sid,'phylogeny',null,null,'selected_sequences',phylo.keySet().sort(),paths(sample,'C',['candidates_phylogeny.fasta']),[field:'C/candidates_phylogeny.fasta'])
            holds(maxCandidates > 0, 'parameters', 'candidate limit available', d('limit'), d('parameters check failed first'))
            boolean plot = c.species.size() > maxCandidates
            def names = files.C[sample]*.name
            present('candidates_identity_boxplot.png', "present only above ${maxCandidates} candidates (${c.species.size()} here)", plot, names.contains('candidates_identity_boxplot.png'))
            if (plot) png(artifact(sample,'C','candidates_identity_boxplot.png'))
            def allowed = ['1.flag','2.flag','7.flag','all_hits.fasta','all_hits.json','query_title.txt',
                'candidates.csv','candidates.json','candidates.fasta','candidates_count.txt','candidates_phylogeny.fasta',
                'assigned_taxonomy.csv','preliminary_id_match.csv','taxa_of_concern_detected.csv','candidates_identity_boxplot.png']
            holds(allowed.containsAll(names), 'candidate folder', 'only known files', d('known files'), names - allowed)
            def f1 = flag(artifact(sample,'C','1.flag'),'1')
            present('assigned_taxonomy.csv', "present only for flag 1A (flag 1 is ${f1[0].value})", f1[0].value == 'A', names.contains('assigned_taxonomy.csv'))
            if (names.contains('assigned_taxonomy.csv')) {
                def assigned = csv(artifact(sample,'C','assigned_taxonomy.csv'))
                same('assigned_taxonomy.csv', 'header equals candidates.csv', table[0], assigned[0])
                same('assigned_taxonomy.csv', 'rows equal candidates.csv', table[1], assigned[1])
            }
        }
        ['1':'conclusion_flag','2':'toi_flag','7':'preliminary_flag'].each { id, field ->
            String owner = owned(sid,'overview_tab',field)
            if (owner) {
                // Selenium checks this flag value: no extra core check that it exists and is valid.
                data(sid,'candidates',null,null,'flag_'+id,null,paths(sample,'C',[id+'.flag']),[field:'C/'+id+'.flag/value',owner:owner])
                return
            }
            check(sid,"C.flag.${id}",'C/'+id+'.flag',paths(sample,'C',[id+'.flag'])) {
                def file = artifact(sample,'C',id+'.flag')
                def rows = flag(file,id)
                same(file.name, 'number of records', count(1, 'record'), count(rows.size(), 'record'))
                same(file.name, 'target', d('no target'), rows[0].target == null && rows[0].target_type == null ? d('no target') : d("${rows[0].target_type}/${rows[0].target}"))
                flagValue(file, id, rows[0])
                data(sid,'candidates',null,null,'flag_'+id,rows[0].value,paths(sample,'C',[id+'.flag']),[field:'C/'+id+'.flag/value'])
            }
        }
        check(sid,'C.toi','C/taxa_of_concern_detected.csv',paths(sample,'C',['taxa_of_concern_detected.csv'])) {
            def expectedTaxa = input.taxa_of_interest.tokenize('|')*.trim()
            boolean exists = files.C[sample]*.name.contains('taxa_of_concern_detected.csv')
            present('taxa_of_concern_detected.csv', "present only when the input lists taxa of interest (${expectedTaxa.size()} here)", !expectedTaxa.isEmpty(), exists)
            if (exists) {
                def table = csv(artifact(sample,'C','taxa_of_concern_detected.csv'))
                same('taxa_of_concern_detected.csv', 'header', ['Taxon of interest','Match rank','Match taxon','Match species','Match accession','Match identity'], table[0])
                same('taxa_of_concern_detected.csv', 'one row per input taxon of interest, in order', expectedTaxa, table[1]*.get('Taxon of interest'))
                holds(candidates[sample] != null, 'taxa_of_concern_detected.csv', 'compared with candidates', d('candidate files valid'), d('candidate files check failed first'))
                table[1].each { row ->
                    if (row['Match accession']) holds(candidates[sample].hits*.accession.contains(row['Match accession']), 'taxa_of_concern_detected.csv',
                                                      'match accession is a candidate hit', d('a candidate accession'), row['Match accession'])
                }
            }
        }
        check(sid,'C.pmi','C/preliminary_id_match.csv',paths(sample,'C',['preliminary_id_match.csv','7.flag'])) {
            def rows = flag(artifact(sample,'C','7.flag'),'7')
            boolean exists = files.C[sample]*.name.contains('preliminary_id_match.csv')
            present('preliminary_id_match.csv', "present only for flag 7A (flag 7 is ${rows[0].value})", rows[0].value == 'A', exists)
            if (exists) {
                def text = artifact(sample,'C','preliminary_id_match.csv').text.replaceAll(/\s+$/, '')
                def pmi = input.preliminary_id.trim()
                def lines = text.readLines()
                holds(lines.size() == 2 && lines[0] == 'rank,taxon' && lines[1].split(',', -1).size() == 2,
                      'preliminary_id_match.csv', 'header line and one data row', d("\"rank,taxon⏎<rank>,${pmi}\""), text)
                def table = csv(artifact(sample,'C','preliminary_id_match.csv'))
                holds(table[1][0].taxon.equalsIgnoreCase(pmi), 'preliminary_id_match.csv', 'taxon is the input preliminary ID', pmi, table[1][0].taxon)
            }
        }
        check(sid,'S.routing-content','S',paths(sample,'S')) {
            holds(candidates.containsKey(sample) && maxCandidates > 0, 'source diversity', 'candidate count available', d('candidate files and parameters valid'), d('an earlier check failed first'))
            def c = candidates[sample]
            boolean assessed = c.species.size() in 1..maxCandidates
            holds(files.S.containsKey(sample), 'source diversity', 'output for this sample', d('output'), d('none'))
            same('source diversity', "files for ${c.species.size()} candidate species (assessed for 1..${maxCandidates})",
                 assessed ? ['4.flag','aggregated_sources.json'] : [], files.S[sample]*.name.sort())
            if (assessed) {
                def sources = json(artifact(sample,'S','aggregated_sources.json'))
                holds(sources instanceof Map, 'aggregated_sources.json', 'maps candidates to sources', d('map'), sources)
                sameSet('aggregated_sources.json', 'one entry per candidate species', c.species*.species, sources.keySet())
                def flagFile = artifact(sample,'S','4.flag')
                def flags = flag(flagFile,'4')
                sameSet('4.flag', 'one record per candidate species', sources.keySet(), flags*.target)
                flags.each { f -> flagValue(flagFile, '4', f) }
                sources.each { taxon, groups ->
                    holds(groups instanceof List && groups.every { it instanceof List }, 'aggregated_sources.json', "${taxon} is a list of source groups", d('list of lists'), groups)
                    def accessions = groups.flatten()*.accession
                    holds(c.hits*.accession.containsAll(accessions), 'aggregated_sources.json', "sources of ${taxon} are candidate hits", d('candidate accessions'), accessions - c.hits*.accession)
                    data(sid,'source_diversity','candidates',taxon,'source_accessions',accessions.unique(false).sort(),
                         paths(sample,'S',['aggregated_sources.json']),[field:'S/aggregated_sources.json/'+taxon])
                    groups.flatten().each { source ->
                        holds(source.accession && source.publications instanceof List && source.is_automated instanceof Boolean, 'aggregated_sources.json',
                              "every source of ${taxon} has accession, publications and is_automated", d('all three'), source)
                    }
                }
                flags.each { f -> data(sid,'source_diversity','candidates',f.target,'flag_4',f.value,paths(sample,'S',['4.flag']),[field:'S/4.flag/'+f.target]) }
            }
        }
        check(sid,'T.labels','T/candidates_phylogeny.nwk',paths(sample,'T')) {
            same('tree output', 'files', count(1, 'file'), count(files.T[sample]?.size() ?: 0, 'file'))
            def tree = artifact(sample,'T','candidates_phylogeny.nwk').text.trim()
            holds(treeSequences.containsKey(sample), 'candidates_phylogeny.nwk', 'compared with selected sequences', d('candidate files valid'), d('candidate files check failed first'))
            def selected = treeSequences[sample].keySet()
            if (selected.isEmpty()) same('candidates_phylogeny.nwk', 'empty when no sequences were selected', '', tree)
            else sameSet('candidates_phylogeny.nwk', 'leaves are the selected sequences plus QUERY', selected.toList() + ['QUERY'], new CoreNewick(tree).leaves())
        }
        coverageChecks(sample,input)
    }
    void coverageChecks(String sample, Map input) {
        def sid = input.sample_id
        check(sid,'D.content','D/db_coverage.json',paths(sample,'D',['db_coverage.json'])) {
            same('coverage output', 'files', count(1, 'file'), count(files.D[sample]?.size() ?: 0, 'file'))
            def coverage = json(artifact(sample,'D','db_coverage.json')).coverage
            holds(coverage instanceof Map, 'db_coverage.json', 'has a coverage section', d('map'), coverage)
            sameSet('db_coverage.json', 'coverage roles', ['candidate','pmi','toi'], coverage.keySet())
            def where = paths(sample,'D',['db_coverage.json'])
            coverage.each { role, taxa ->
                holds(taxa instanceof Map, 'db_coverage.json', "${role} maps taxa to results", d('map'), taxa)
                data(sid,'database_coverage',null,null,role+'_taxa',taxa.keySet().sort(),where,[field:"D/coverage/${role}"])
                taxa.each { taxon, values ->
                    holds(values instanceof Map && values.keySet().containsAll(['target','related','country']), 'db_coverage.json',
                          "${role}/${taxon} has target, related and country", ['target','related','country'], values instanceof Map ? values.keySet() : values)
                    holds(values.target == null || values.target instanceof Number && values.target >= 0 && values.target == values.target.toInteger(),
                          'db_coverage.json', "${role}/${taxon} target count", d('whole number or null'), values.target)
                    data(sid,'database_coverage',role,taxon,'target_state',values.containsKey('not_assessed') ? 'not_assessed' : values.target == null ? 'null' : 'assessed',
                         where,[field:"D/coverage/${role}/${taxon}/target"])
                    // Record counts are live GenBank/BOLD numbers: Selenium owns them (±10%); core only reports them.
                    data(sid,'database_coverage',role,taxon,'target_record_count',values.target,where,
                         [field:"D/coverage/${role}/${taxon}/target",owner:owned(sid,'database_coverage','record_count',role,taxon)])
                    ['related','country'].each { field ->
                        def counts = values[field]
                        holds(counts == null || counts instanceof Map || field == 'country' && counts == 'NA', 'db_coverage.json',
                              "${role}/${taxon}/${field}", d(field == 'country' ? 'species list, NA or null' : 'species list or null'), counts)
                        if (counts instanceof Map) {
                            counts.each { species, n ->
                                holds(n == null || n instanceof Number && n >= 0 && n == n.toInteger(), 'db_coverage.json',
                                      "${role}/${taxon}/${field}/${species} count", d('whole number or null'), n)
                            }
                            // In-country species names must match; per-species counts are deliberately not compared (user decision 2026-11-23).
                            // Related-species names are not compared for any role (user decision 2026-11-25).
                            if (field == 'related') return
                            data(sid,'database_coverage',role,taxon,field+'_species',counts.keySet().sort(),where,[field:"D/coverage/${role}/${taxon}/${field}"])
                        } else data(sid,'database_coverage',role,taxon,field+'_state',counts == null ? 'null' : 'NA',where,[field:"D/coverage/${role}/${taxon}/${field}"])
                    }
                }
            }
        }
        ['5.1','5.2','5.3'].each { id ->
            check(sid,"F.${id}.records",'F/'+id+'.flag',paths(sample,'F',[id+'.flag'])+paths(sample,'D',['db_coverage.json'])) {
                sameSet('coverage flags', 'file names', ['5.1.flag','5.2.flag','5.3.flag'], files.F[sample]*.name)
                def file = artifact(sample,'F',id+'.flag')
                def rows = flag(file,id)
                def coverage = json(artifact(sample,'D','db_coverage.json')).coverage
                // Structure is always checked: Selenium reads only the taxa it shows, not missing/extra/duplicate records.
                sameSet(file.name, 'one record per taxon in db_coverage.json', coverage.collectMany { role, taxa -> taxa.keySet().collect { role+'/'+it } },
                        rows.collect { it.target_type+'/'+it.target })
                rows.each { f ->
                    def owner = id == '5.3' ? null : owned(sid,'database_coverage',id == '5.1' ? 'flag_text1':'flag_text2',f.target_type,f.target)
                    // The value itself is checked here only where Selenium does not check it.
                    if (!owner) flagValue(file, id, f)
                    data(sid,'coverage_flags',f.target_type,f.target,'flag_'+id.replace('.','_'),f.value,paths(sample,'F',[id+'.flag']),
                         [field:"F/${id}/${f.target_type}/${f.target}",owner:owner])
                }
            }
        }
        check(sid,'M.files','M/maps',paths(sample,'M')) {
            def maps = files.M[sample] ?: []
            data(sid,'maps',null,null,'filenames',maps*.name.sort(),paths(sample,'M'),[field:'M/map filenames'])
            maps.each { f ->
                holds(f.name ==~ /map.*\.png/, f.name, 'map file name', d('map*.png'), f.name)
                holds(f.isFile(), f.name, 'listed map exists', d('file present'), d('file missing'))
                png(f)
            }
        }
    }
}

/** Small recursive Newick reader: validates grammar, branch lengths and duplicate leaves. */
class CoreNewick {
    static final String WHERE = 'candidates_phylogeny.nwk'
    String text; int pos=0; List labels=[]
    CoreNewick(String text) { this.text=text }
    void space() { while (pos<text.size() && Character.isWhitespace(text.charAt(pos))) pos++ }
    void expect(boolean ok, String rule, String expected) {
        CoreAssertions.holds(ok, WHERE, rule, CoreAssertions.d(expected), CoreAssertions.d("at character ${pos}: ${text.drop(Math.max(0, pos - 20)).take(40)}"))
    }
    String label() {
        space(); int start=pos
        if (pos<text.size() && text[pos]=="'") {
            pos++; def value=''
            while (pos<text.size()) {
                if (text[pos]=="'") { pos++; if (pos<text.size() && text[pos]=="'") { value+="'";pos++ } else return value }
                else value+=text[pos++]
            }
            expect(false, 'quoted label is closed', "closing '")
        }
        while(pos<text.size() && !(text[pos] in [':',',','(',')',';']) && !Character.isWhitespace(text.charAt(pos))) pos++
        text.substring(start,pos)
    }
    void node() {
        space(); expect(pos<text.size(), 'complete tree', 'more tree text')
        if (text[pos]=='(') {
            pos++;node();space();expect(text[pos]==',', 'groups have at least two members', ',')
            while (text[pos]==',') { pos++;node();space() }
            expect(text[pos]==')', 'balanced brackets', ')');pos++;label()
        } else { def value=label();expect(value as boolean, 'every leaf has a name', 'a leaf name');labels<<value }
        space()
        if (pos<text.size() && text[pos]==':') {
            pos++;int start=pos
            while(pos<text.size() && !(text[pos] in [',',')',';'])) pos++
            double length=Double.parseDouble(text.substring(start,pos).trim());expect(Double.isFinite(length), 'branch length is a number', 'finite number')
        }
    }
    List leaves() {
        node();space()
        expect(pos==text.size()-1 && text[pos]==';', 'ends with a single ;', ';')
        CoreAssertions.unique(WHERE, 'each leaf name appears once', labels)
        labels
    }
}

// Must not be the first class: callers load this file with parseClass(), which returns the first class.
/** Plain description used as an Expected/Actual value (printed without quotes). */
class Desc {
    String text
    String toString() { text }
    boolean equals(Object other) { other instanceof Desc && other.text == text }
    int hashCode() { text.hashCode() }
}
