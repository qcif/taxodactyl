// Run with nf-test 0.9.5's bundled Groovy (see README). All inputs are synthetic.
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.nio.file.Files

def source = new File(args ? args[0] : '.').canonicalFile
def loader = new GroovyClassLoader(this.class.classLoader)
def klass = loader.parseClass(new File(source,'test/core/CoreAssertions.groovy'))
def temp = Files.createTempDirectory('core-contracts-').toFile()
def root = new File(temp,'repo'); new File(root,'test/core').mkdirs();new File(root,'test/selenium/expected').mkdirs()
new File(root,'test/core/CoreAssertions.groovy').bytes=new File(source,'test/core/CoreAssertions.groovy').bytes
def sample='query_001_Synthetic'
new File(root,'test/core/metadata.csv').text='sample_id,preliminary_id,taxa_of_interest\nSynthetic,Taxon,Taxon\n'
def make = { channel, name, content ->
    def f=new File(temp,"${channel}/${sample}/${name}");f.parentFile.mkdirs()
    f.text=content instanceof String ? content : JsonOutput.toJson(content)
    f.toString()
}
def flags={ id -> ['pmi','toi'].collect { [flag_id:id,value:'B',target:'Taxon',target_type:it] } }
def h = [make('H','all_hits.fasta',''),make('H','all_hits.json',[query_title:'Synthetic',query_length:3,hits:[]]),make('H','query_title.txt','Synthetic')]
def c = ['all_hits.fasta','all_hits.json','query_title.txt'].collect { name -> make('C',name,new File(h.find { it.endsWith('/'+name) }).text) }
c += ['1':'E','2':'B','7':'NA'].collect { id,value -> make('C',id+'.flag',[[flag_id:id,value:value,target:null,target_type:null]]) }
c += [make('C','candidates.csv','species,taxid,accession,hit_subject,identity,query_coverage,alignment_length,e_value,bitscore\n'),
 make('C','candidates.json',[hits:[],species:[],hit_counts:[:]]),make('C','candidates.fasta',''),
 make('C','candidates_count.txt','0'),make('C','candidates_phylogeny.fasta',''),
 make('C','taxa_of_concern_detected.csv','Taxon of interest,Match rank,Match taxon,Match species,Match accession,Match identity\nTaxon,,,,,\n')]
def coverage=[coverage:[candidate:[:],pmi:[Taxon:[target:10,related:[:],country:null]],toi:[Taxon:[target:10,related:[:],country:null]]]]
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
def invariantFails={ data -> data.rows.findAll { !it.promotable && it.status in ['failed','error'] } }
int passed=0
def expect={ name, body -> body.call();passed++;println("PASS ${name}") }
try {
 def initial=run()
 expect('empty/skipped valid; observations unbaselined') {
    assert invariantFails(initial[0]).isEmpty() : invariantFails(initial[0])
    assert initial[0].rows.any { it.status=='unbaselined' }
 }
 // Only disposable synthetic data are accepted here; no real expectations are written.
 def entries=[:]
 initial[0].rows.findAll { it.promotable }.each { row -> entries.computeIfAbsent(row.sample) { [:] }[row.id]=[value:row.observed] }
 new File(root,'test/core/expectations.json').text=JsonOutput.toJson([schema_version:1,entries:entries])
 expect('reviewed synthetic baseline passes') { assert run()[1].isEmpty() }
 def original=channels.ch_hits_for_report
 channels.ch_hits_for_report=[]
 expect('missing sample') { assert run()[0].rows.find { it.id=='H.routing' }.status=='failed' }
 channels.ch_hits_for_report=original+original
 expect('duplicate sample') { assert run()[0].rows.find { it.id=='H.routing' }.status=='failed' }
 channels.ch_hits_for_report=[['query_001_Wrong',h]]
 expect('wrong sample association') { assert run()[0].rows.find { it.id=='H.routing' }.status=='failed' }
 channels.ch_hits_for_report=original
 def hitsFile=new File(h.find { it.endsWith('all_hits.json') });def hitsText=hitsFile.text
 hitsFile.text='{broken'
 expect('malformed output is error, never pass') { assert run()[0].rows.find { it.id=='H.files' }.status=='error' }
 hitsFile.text=hitsText
 def flagFile=new File(f[0]);def originalFlags=flagFile.text
 def values=new JsonSlurper().parse(flagFile);values[0].value='C';flagFile.text=JsonOutput.toJson(values)
 expect('changed 5.1 value with unchanged count') { assert run()[0].rows.find { it.id=='F.value/5.1/pmi/Taxon' }.status=='failed' }
 flagFile.text=originalFlags
 values=new JsonSlurper().parse(flagFile);values[1]=values[0];flagFile.text=JsonOutput.toJson(values)
 expect('duplicate target replacing another role') { assert run()[0].rows.find { it.id=='F.5.1.records' }.status=='failed' }
 flagFile.text=JsonOutput.toJson(flags('5.1').take(1))
 expect('missing flag record') { assert run()[0].rows.find { it.id=='F.5.1.records' }.status=='failed' }
 flagFile.text=JsonOutput.toJson(flags('5.1')+[[flag_id:'5.1',value:'B',target:'Extra',target_type:'pmi']])
 expect('extra flag record') { assert run()[0].rows.find { it.id=='F.5.1.records' }.status=='failed' }
 flagFile.text=originalFlags
 coverage.coverage.pmi.Taxon.target=11;new File(d).text=JsonOutput.toJson(coverage)
 expect('count-only drift preserves flag values') {
    def result=run()[0]
    assert result.rows.find { it.id=='D.count/pmi/Taxon/target' }.status=='failed'
    assert result.rows.find { it.id=='F.value/5.1/pmi/Taxon' }.status=='passed'
 }
 hitsFile.text='{broken'
 expect('multiple independent failures survive') {
    def result=run()[0]
    assert result.rows.find { it.id=='D.count/pmi/Taxon/target' }.status=='failed'
    assert result.rows.find { it.id=='H.files' }.status=='error'
 }
 hitsFile.text=hitsText
 coverage.coverage.pmi.Taxon.target=10;new File(d).text=JsonOutput.toJson(coverage)
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
 coverage.coverage.pmi.Taxon.target=99;new File(d).text=JsonOutput.toJson(coverage)
 expect('populated Selenium count owns drift without duplicate core expectation') {
    def result=run()[0]
    def row=result.rows.find { it.id=='D.count/pmi/Taxon/target' }
    assert row.status=='delegated' && !row.promotable && row.owner.contains('record_count')
    assert result.rows.find { it.id=='F.value/5.1/pmi/Taxon' }.status=='delegated'
 }
 fixture.text=fixture.text.replace("value: ['10']", "value: ['']")
 expect('empty Selenium expectation is not coverage') {
    assert run()[0].rows.find { it.id=='D.count/pmi/Taxon/target' }.status=='failed'
 }
 fixture.delete()
 coverage.coverage.pmi.Taxon.target=10;new File(d).text=JsonOutput.toJson(coverage)
 def countFile=new File(c.find { it.endsWith('candidates_count.txt') });countFile.delete()
 expect('missing output differs from legitimate empty output') { assert run()[0].rows.find { it.id=='C.content' }.status=='failed' }
 println "${passed} synthetic contract scenarios passed"
} finally { temp.deleteDir() }
