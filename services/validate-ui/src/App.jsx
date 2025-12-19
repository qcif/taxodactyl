import { useState } from 'react';
import CsvEditor from './components/CsvEditor';

function App() {
  const [metadataFile, setMetadataFile] = useState(null);
  const [fastaFile, setFastaFile] = useState(null);
  const [editedCsvText, setEditedCsvText] = useState(null);
  const [errors, setErrors] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [validated, setValidated] = useState(false);
  const [errorRows, setErrorRows] = useState([]);

  const handleValidate = async () => {
    if (!fastaFile) {
      alert("Please select FASTA file");
      return;
    }

    const formData = new FormData();
    if (editedCsvText) {
      formData.append("metadata_text", editedCsvText); // edited CSV
    } else if (metadataFile) {
      formData.append("metadata_csv", metadataFile); // initial upload
    } else {
      alert("Please select a CSV file");
      return;
    }
    formData.append("query_fasta", fastaFile);

    setValidated(false);
    setErrors(null);
    setErrorRows([]);

    const res = await fetch("http://127.0.0.1:8000/validate", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (res.ok) {
      setValidated(true);
      setCsvText(data.metadata_csv || "");
      setErrorRows([]);
    } else {
      setErrors(data.error);
      setCsvText(data.metadata_csv || "");
      setEditedCsvText(data.metadata_csv);
      setErrorRows(data.rows || []);
    }
  };



  return (
    <div style={{ padding: '20px', maxWidth: '900px', margin: '0 auto' }}>
      <h1>TAXON p0 Validator</h1>

      <div>
        <label>Metadata CSV</label>
        <input type="file" accept=".csv" onChange={e => setMetadataFile(e.target.files[0])} />
      </div>

      <div>
        <label>Query FASTA</label>
        <input type="file" accept=".fasta,.fa" onChange={e => setFastaFile(e.target.files[0])} />
      </div>

      <button onClick={() => handleValidate()}>Validate</button>

      {validated && <div style={{ color: 'green', marginTop: '20px' }}>✔ Validation Passed</div>}

      {errors && (
        <div style={{ color: 'red', marginTop: '20px' }}>
          <h3>Validation Errors:</h3>
          <pre>{errors.message}</pre>
          <CsvEditor 
            csvText={csvText} 
            onSave={handleValidate} 
            errorRows={errorRows}
            onChange={setEditedCsvText}
          />
        </div>
      )}
    </div>
  );
}

export default App;
