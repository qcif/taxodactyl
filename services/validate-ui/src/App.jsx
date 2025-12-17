// import { useState } from 'react'
// import reactLogo from './assets/react.svg'
// import viteLogo from '/vite.svg'
// import './App.css'

// function App() {
//   const [count, setCount] = useState(0)

//   return (
//     <>
//       <div>
//         <a href="https://vite.dev" target="_blank">
//           <img src={viteLogo} className="logo" alt="Vite logo" />
//         </a>
//         <a href="https://react.dev" target="_blank">
//           <img src={reactLogo} className="logo react" alt="React logo" />
//         </a>
//       </div>
//       <h1>Vite + React</h1>
//       <div className="card">
//         <button onClick={() => setCount((count) => count + 1)}>
//           count is {count}
//         </button>
//         <p>
//           Edit <code>src/App.jsx</code> and save to test HMR
//         </p>
//       </div>
//       <p className="read-the-docs">
//         Click on the Vite and React logos to learn more
//       </p>
//     </>
//   )
// }

// export default App

import { useState } from 'react';
import CsvEditor from './components/CsvEditor';

function App() {
  const [metadataFile, setMetadataFile] = useState(null);
  const [fastaFile, setFastaFile] = useState(null);
  // const [taxdbDir, setTaxdbDir] = useState('');
  const [errors, setErrors] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [validated, setValidated] = useState(false);
  const [errorRows, setErrorRows] = useState([]);

  const handleSubmit = async () => {
    if (!metadataFile || !fastaFile) {
      alert('Please select both files');
      return;
    }
    setValidated(false);
    setErrors(null);
    setErrorRows([]);

    const formData = new FormData();
    formData.append('metadata_csv', metadataFile);
    formData.append('query_fasta', fastaFile);
    // if (taxdbDir) formData.append('taxdb_dir', taxdbDir);

    const res = await fetch('http://127.0.0.1:8000/validate', {
      method: 'POST',
      body: formData
    });

    if (res.ok) {
      setValidated(true);
      setCsvText(await metadataFile.text());
    } else {
      const data = await res.json();
      setErrors(data.error);
      setCsvText(data.metadata_csv || '');
      setErrorRows(data.rows || []);
    }
  };

  const handleRevalidate = async (updatedCsvText) => {
    if (!fastaFile) return;

    const formData = new FormData();
    formData.append('metadata_text', updatedCsvText);
    formData.append('query_fasta', fastaFile);
    // if (taxdbDir) formData.append('taxdb_dir', taxdbDir);

    const res = await fetch('http://127.0.0.1:8000/revalidate', {
      method: 'POST',
      body: formData
    });

    if (res.ok) {
      setValidated(true);
      setErrors(null);
      setCsvText(updatedCsvText);
      setErrorRows([]);
    } else {
      const data = await res.json();
      setErrors(data.error);
      setCsvText(updatedCsvText);
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

      {/* <div>
        <label>TaxDB Dir</label>
        <input type="text" value={taxdbDir} onChange={e => setTaxdbDir(e.target.value)} />
      </div> */}

      <button onClick={handleSubmit}>Validate</button>

      {validated && <div style={{ color: 'green', marginTop: '20px' }}>✔ Validation Passed</div>}

      {errors && (
        <div style={{ color: 'red', marginTop: '20px' }}>
          <h3>Validation Errors:</h3>
          <pre>{errors.message}</pre>
          <CsvEditor 
            csvText={csvText} 
            onSave={handleRevalidate} 
            errorRows={errorRows}/>
        </div>
      )}
    </div>
  );
}

export default App;
