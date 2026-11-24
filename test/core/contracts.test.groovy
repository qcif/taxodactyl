// Run with nf-test 0.9.5's bundled Groovy (see README). All inputs are synthetic.
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.nio.file.Files
import org.yaml.snakeyaml.DumperOptions
import org.yaml.snakeyaml.Yaml

def source = new File(args ? args[0] : '.').canonicalFile
def loader = new GroovyClassLoader(this.class.classLoader)
def klass = loader.parseClass(new File(source,'test/core/CoreAssertions.groovy'))
def temp = Files.createTempDirectory('core-contracts-').toFile()
def root = new File(temp,'repo'); new File(root,'test/core/expected').mkdirs();new File(root,'test/selenium/expected').mkdirs()
['CoreAssertions.groovy','schema.yaml'].each { new File(root,'test/core/'+it).bytes=new File(source,'test/core/'+it).bytes }
def sample='query_001_Synthetic'
new File(root,'test/core/metadata.csv').text='sample_id,preliminary_id,taxa_of_interest\nSynthetic,Taxon,Taxon\n'
def make = { channel, name, content ->
    def f=new File(temp,"${channel}/${sample}/${name}");f.parentFile.mkdirs()
    f.text=content instanceof String ? content : JsonOutput.toJson(content)
    f.toString()
}
def flags={ id -> ['pmi','toi'].collect { [flag_id:id,value:'B',target:'Taxon',target_type:it] } }
def hit = { seq -> [accession:'ACC1',hit_id:'h1',hit_subject:'s',identity:0.9,hsps:[[alignment:"Query  1  ${seq}  4\n          ||||\nSbjct  1  ${seq}  4"]],
                   alignment_length:4,query_coverage:1,bitscore:1,e_value:0] }
def hitsJson = { seq -> [query_title:'Synthetic',query_length:4,hits:[hit(seq)]] }
def h = [make('H','all_hits.fasta','>ACC1\nACGT\n'),make('H','all_hits.json',hitsJson('ACGT')),make('H','query_title.txt','Synthetic')]
def c = ['all_hits.fasta','all_hits.json','query_title.txt'].collect { name -> make('C',name,new File(h.find { it.endsWith('/'+name) }).text) }
c += ['1':'E','2':'B','7':'NA'].collect { id,value -> make('C',id+'.flag',[[flag_id:id,value:value,target:null,target_type:null]]) }
c += [make('C','candidates.csv','species,taxid,accession,hit_subject,identity,query_coverage,alignment_length,e_value,bitscore\n'),
 make('C','candidates.json',[hits:[],species:[],hit_counts:[:]]),make('C','candidates.fasta',''),
 make('C','candidates_count.txt','0'),make('C','candidates_phylogeny.fasta',''),
 make('C','taxa_of_concern_detected.csv','Taxon of interest,Match rank,Match taxon,Match species,Match accession,Match identity\nTaxon,,,,,\n')]
def coverage=[coverage:[candidate:[:],pmi:[Taxon:[target:10,related:[Sp1:3,Sp2:4],country:null]],toi:[Taxon:[target:10,related:[Sp1:3,Sp2:4],country:'NA']]]]
def d=make('D','db_coverage.json',coverage)
def f=['5.1','5.2','5.3'].collect { make('F',it+'.flag',flags(it)) }
def channels=[ch_hits_for_report:[[sample,h]],ch_candidates_for_report:[[sample,c]],
 ch_source_diversity_for_report:[[sample,[]]],ch_homology_trees:[[sample,make('T','candidates_phylogeny.nwk','')]],
 ch_db_coverage_json:[[sample,d]],ch_db_coverage_flags:[[sample,f]],ch_db_coverage_maps:[],ch_html_report:[],
 ch_collated_versions:[make('V','software_versions.yml','BLAST:\n  blast: 1\nMAFFT:\n  mafft: 1\nFASTME:\n  fastme: 1\n')],
 ch_params_json:[make('P','params.json',[max_candidates_for_analysis:3,db_type:'blast_core_nt'])],
 ch_workflow_timestamp:[make('W','timestamp.txt','20261123 043225')]]
def output=new File(temp,'assertions.json')
def run = {
    def evaluator=klass.newInstance(root,output,[id:'synthetic',source_test:'contracts.test.groovy',execution_success:true])
    evaluator.prepare(channels,true)
    def failures=[]
    evaluator.evaluate().each { try { it.call() } catch(Throwable e) { failures<<e } }
    [new JsonSlurper().parse(output), failures]
}
def rowOf = { result, id -> result[0].rows.find { it.id==id } }
def expectedFile = new File(root,'test/core/expected/1_Synthetic.yaml')
// Minimal stand-in for `testkit.py ingest` (synthetic data only; real files go through the reviewed CLI).
def writeExpected = { rows ->
    def comps = [:]
    rows.findAll { it.promotable }.each { r ->
        def comp = comps.computeIfAbsent(r.component) { [id:r.component] }
        def target = r.group ? comp.computeIfAbsent(r.group) { [] }.with { list -> list.find { it.name==r.name } ?: [name:r.name,assertions:[]].tap { list << it } }.assertions
                             : comp.computeIfAbsent('assertions') { [] }
        target << [id:r.assertion,type:r.kind,value:r.observed]
    }
    def options = new DumperOptions(); options.defaultFlowStyle = DumperOptions.FlowStyle.BLOCK
    expectedFile.text = new Yaml(options).dump([sample_id:'Synthetic',components:comps.values().toList()])
}
def invariantFails={ data -> data.rows.findAll { it.kind == null && it.status in ['failed','error'] } }
int passed=0
def expect={ name, body -> body.call();passed++;println("PASS ${name}") }
try {
 def initial=run()
 expect('empty/skipped valid; new sample without file is unbaselined and fails') {
    assert invariantFails(initial[0]).isEmpty() : invariantFails(initial[0])
    assert initial[0].rows.any { it.status=='unbaselined' } && !initial[1].isEmpty()
    assert initial[0].expectations == [Synthetic:null]
 }
 writeExpected(initial[0].rows)
 def baseline = expectedFile.text
 expect('reviewed synthetic baseline passes; file digest recorded') {
    def result=run()
    assert result[1].isEmpty() : result[1]*.message
    assert result[0].expectations.Synthetic.file == 'test/core/expected/1_Synthetic.yaml'
 }
 def original=channels.ch_hits_for_report
 channels.ch_hits_for_report=[]
 expect('missing sample') { assert rowOf(run(),'H.routing').status=='failed' }
 channels.ch_hits_for_report=original+original
 expect('duplicate sample') { assert rowOf(run(),'H.routing').status=='failed' }
 channels.ch_hits_for_report=[['query_001_Wrong',h]]
 expect('wrong sample association') { assert rowOf(run(),'H.routing').status=='failed' }
 channels.ch_hits_for_report=original
 def hitsFile=new File(h.find { it.endsWith('all_hits.json') });def hitsText=hitsFile.text
 hitsFile.text='{broken'
 expect('malformed output is error, never pass; no stale cascade') {
    def result=run()
    assert rowOf(result,'H.files').status=='error'
    assert !result[0].rows.any { it.absent && it.component=='blast_hits' }
 }
 hitsFile.text=hitsText
 def rewriteHits = { seq ->
    [h,c].each { list ->
        new File(list.find { it.endsWith('all_hits.fasta') }).text=">ACC1\n${seq}\n"
        new File(list.find { it.endsWith('all_hits.json') }).text=JsonOutput.toJson(hitsJson(seq))
    }
 }
 rewriteHits('ACGA')
 expect('changed hit sequence fails its fingerprint only') {
    def result=run()
    def row=rowOf(result,'blast_hits/sequence_fingerprints')
    assert row.status=='failed' && row.detail.ACC1=='ACGA'
    assert invariantFails(result[0]).isEmpty()
    assert rowOf(result,'blast_hits/accessions').status=='passed'
 }
 rewriteHits('ACGT')
 def flagFile=new File(f[0]);def originalFlags=flagFile.text
 def values=new JsonSlurper().parse(flagFile);values[0].value='C';flagFile.text=JsonOutput.toJson(values)
 expect('changed 5.1 value with unchanged record count') { assert rowOf(run(),'coverage_flags/pmi/Taxon/flag_5_1').status=='failed' }
 flagFile.text=originalFlags
 values=new JsonSlurper().parse(flagFile);values[1]=values[0];flagFile.text=JsonOutput.toJson(values)
 expect('duplicate target replacing another role') { assert rowOf(run(),'F.5.1.records').status=='failed' }
 flagFile.text=JsonOutput.toJson(flags('5.1').take(1))
 expect('missing flag record') { assert rowOf(run(),'F.5.1.records').status=='failed' }
 flagFile.text=JsonOutput.toJson(flags('5.1')+[[flag_id:'5.1',value:'B',target:'Extra',target_type:'pmi']])
 expect('extra flag record') { assert rowOf(run(),'F.5.1.records').status=='failed' }
 flagFile.text=originalFlags
 coverage.coverage.pmi.Taxon.target=11;coverage.coverage.pmi.Taxon.related=[Sp1:30,Sp2:40];new File(d).text=JsonOutput.toJson(coverage)
 expect('record counts are not core expectations (target and per-species)') {
    def result=run()
    assert result[1].isEmpty() : result[1]*.message
    assert rowOf(result,'database_coverage/pmi/Taxon/target_record_count').status=='not_checked'
    assert !result[0].rows.any { it.id.contains('Sp1') }
 }
 coverage.coverage.pmi.Taxon.related=[Sp1:3,Sp3:4];new File(d).text=JsonOutput.toJson(coverage)
 expect('related species names must match') {
    def result=run()
    assert rowOf(result,'database_coverage/pmi/Taxon/related_species').status=='failed'
    assert rowOf(result,'database_coverage/toi/Taxon/related_species').status=='passed'
 }
 coverage.coverage.pmi.Taxon.related=[Sp1:3,Sp2:'x'];new File(d).text=JsonOutput.toJson(coverage)
 expect('count structure is still an invariant') { assert rowOf(run(),'D.content').status=='failed' }
 coverage.coverage.pmi.Taxon.related=[Sp1:3,Sp2:4];coverage.coverage.pmi.Taxon.target=10;new File(d).text=JsonOutput.toJson(coverage)
 hitsFile.text='{broken';flagFile.text=JsonOutput.toJson(flags('5.1').collect { it + [value:'C'] })
 expect('multiple independent failures survive') {
    def result=run()
    assert rowOf(result,'coverage_flags/pmi/Taxon/flag_5_1').status=='failed'
    assert rowOf(result,'H.files').status=='error'
 }
 hitsFile.text=hitsText;flagFile.text=originalFlags
 def fixture = new File(root,'test/selenium/expected/synthetic.yaml')
 fixture.text = """sample_id: Synthetic
components:
- id: database_coverage
  pmi:
  - assertions:
    - id: title
      value: ['Database coverage of Preliminary Morphology ID Taxon']
    - id: record_count
      value: ['10']
    - id: flag_text1
      value: ['5.1B']
"""
 expect('Selenium-owned value is delegated; a still-stored core entry must be removed') {
    def result=run()
    assert rowOf(result,'database_coverage/pmi/Taxon/target_record_count').status=='delegated'
    def row=rowOf(result,'coverage_flags/pmi/Taxon/flag_5_1')
    assert row.absent && row.status=='failed' && row.promotable && row.diagnostic.contains('synthetic.yaml')
 }
 fixture.text=fixture.text.replace("value: ['10']", "value: ['']")
 expect('empty Selenium expectation is not ownership; count stays unchecked, not failed') {
    assert rowOf(run(),'database_coverage/pmi/Taxon/target_record_count').status=='not_checked'
 }
 fixture.delete()
 def doc=new Yaml().load(baseline)
 doc.components.find { it.id=='database_coverage' }.pmi << [name:'Gone',assertions:[[id:'target_state',type:'state',value:'assessed']]]
 expectedFile.text=new Yaml().dump(doc)
 expect('stored entry with no observation is reported (stale), not ignored') {
    def result=run()
    def stale=rowOf(result,'database_coverage/pmi/Gone/target_state')
    assert stale?.absent && stale.status=='failed' && stale.promotable && rowOf(result,'expected.files').status=='passed' : result[0].rows.findAll { it.status!='passed' }
 }
 expectedFile.text=baseline
 def overview = new File(root,'test/selenium/expected/synthetic.yaml')
 overview.text = '''sample_id: Synthetic
components:
- id: overview_tab
  assertions:
  - id: conclusion_flag
    value: Flag 1E
- id: database_coverage
  pmi:
  - assertions:
    - id: title
      value: ['Database coverage of Preliminary Morphology ID Taxon']
    - id: flag_text1
      value: ['5.1B']
'''
 def flag1=new File(c.find { it.endsWith('1.flag') }); def flag1Text=flag1.text
 values=new JsonSlurper().parse(flagFile); values.each { it.value='Z' }; flagFile.text=JsonOutput.toJson(values)
 expect('Selenium-owned flags get no extra core validity check; unowned ones do') {
    def result=run()
    assert !result[0].rows.any { it.id=='C.flag.1' }
    assert rowOf(result,'C.flag.2').status=='passed'
    assert rowOf(result,'candidates/flag_1').status in ['delegated','failed']
    def records=rowOf(result,'F.5.1.records')
    assert records.status=='failed' && records.diagnostic.startsWith('5.1.flag: flag 5.1 value for toi/Taxon\nExpected: one of A/B/C/NA/ERR\nActual: "Z"')
    assert !records.diagnostic.contains('pmi/Taxon')
 }
 values=new JsonSlurper().parse(flagFile); values.find { it.target_type=='toi' }.value='B'; values.find { it.target_type=='pmi' }.value='Z'; flagFile.text=JsonOutput.toJson(values)
 expect('an invalid value Selenium checks is left to Selenium; structure still checked') {
    def result=run()
    assert rowOf(result,'F.5.1.records').status=='passed'
    flagFile.text=JsonOutput.toJson(values.take(1))
    assert rowOf(run(),'F.5.1.records').diagnostic.startsWith('5.1.flag: one record per taxon in db_coverage.json')
 }
 flagFile.text=originalFlags; flag1.text=flag1Text; overview.delete()
 def orphan=new File(root,'test/core/expected/2_Other.yaml'); orphan.text='sample_id: Other\ncomponents: []\n'
 expect('orphan file fails with its name') {
    def row=rowOf(run(),'expected.files'); assert row.status=='failed' && row.diagnostic.contains('2_Other.yaml') && row.diagnostic.contains('orphan')
 }
 orphan.text='sample_id: Synthetic\ncomponents: []\n'
 expect('duplicate sample_id fails') { assert rowOf(run(),'expected.files').diagnostic.contains('duplicate sample_id') }
 orphan.delete()
 expectedFile.text=baseline+'- id: maps\n  assertions:\n  - id: pixels\n    value: 1\n'
 expect('unknown assertion fails') { assert rowOf(run(),'expected.files').diagnostic.contains('unknown or unstorable assertion pixels') }
 expectedFile.text=baseline
 def flag7=new File(c.find { it.endsWith('7.flag') }); def flag7Text=flag7.text
 flag7.text=JsonOutput.toJson([[flag_id:'7',value:'A',target:null,target_type:null]])
 def pmi=make('C','preliminary_id_match.csv','rank,taxongenus,Taxon'); c << pmi
 expect('PMI CSV with joined lines explains itself in plain words') {
    def row=rowOf(run(),'C.pmi')
    assert row.status=='failed'
    assert row.diagnostic.startsWith('preliminary_id_match.csv: header line and one data row\nExpected: "rank,taxon⏎<rank>,Taxon"\nActual: "rank,taxongenus,Taxon"')
 }
 new File(pmi).text='rank,taxon\ngenus,Taxon\n'
 expect('well-formed PMI CSV passes') { assert rowOf(run(),'C.pmi').status=='passed' }
 c.remove(pmi); new File(pmi).delete(); flag7.text=flag7Text
 channels.ch_hits_for_report=[]
 expect('routing failure names missing samples') {
    assert rowOf(run(),'H.routing').diagnostic.startsWith('ch_hits_for_report: one entry for every sample in metadata.csv\nExpected: ["query_001_Synthetic"]\nActual: []\nDifference: missing ["query_001_Synthetic"]; unexpected []')
 }
 channels.ch_hits_for_report=original
 def countFile=new File(c.find { it.endsWith('candidates_count.txt') });countFile.delete()
 expect('missing output differs from legitimate empty output, with a plain message') {
    def row=rowOf(run(),'C.content')
    assert row.status=='failed' && row.diagnostic.startsWith('candidates_count.txt: listed output file exists\nExpected: file present\nActual: missing: ')
 }
 println "${passed} synthetic contract scenarios passed"
} finally { temp.deleteDir() }
