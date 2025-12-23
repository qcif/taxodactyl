import { useState } from 'react';
import JSZip from "jszip";
import Papa from "papaparse";
import CsvEditor from './components/CsvEditor';

function App() {
  const [metadataFile, setMetadataFile] = useState(null);
  const [fastaFile, setFastaFile] = useState(null);
  const [editedCsvText, setEditedCsvText] = useState(null);
  const [errors, setErrors] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [fastaText, setFastaText] = useState('');
  const [validated, setValidated] = useState(false);
  const [errorRows, setErrorRows] = useState([]);
  const [showDownloadWarning, setShowDownloadWarning] = useState(false);
  const MAX_SEQ_LIMIT = 149
  
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
      setFastaText(data.query_fasta || "");
      setErrorRows([]);
      setShowDownloadWarning(
        data.message?.toLowerCase().includes("auto-fixed")
  );
    } else {
      setErrors(data.error);
      setCsvText(data.metadata_csv || "");
      setEditedCsvText(data.metadata_csv);
      setErrorRows(data.rows || []);
    }
  };

  const downloadFile = (content, filename, mime) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const splitFasta = (fastaText, seqsPerFile = 150) => {
    const records = fastaText
      .split(/^>/m)
      .filter(r => r.trim() !== "")
      .map(r => ">" + r.trim());

    const chunks = [];
    for (let i = 0; i < records.length; i += seqsPerFile) {
      chunks.push(records.slice(i, i + seqsPerFile));
    }

    return chunks;
  };


  const downloadCsvAsZip = async (csvText, rowsPerFile = MAX_SEQ_LIMIT) => {
    const parsed = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true
    });

    const header = parsed.meta.fields;
    const rows = parsed.data;

    const zip = new JSZip();

    for (let i = 0; i < rows.length; i += rowsPerFile) {
      const chunk = rows.slice(i, i + rowsPerFile);

      const csvChunk = Papa.unparse({
        fields: header,
        data: chunk
      });

      const fileIndex = Math.floor(i / rowsPerFile) + 1;
      zip.file(
        `validated_metadata_part${fileIndex}.csv`,
        csvChunk
      );
    }

    const fastaChunks = splitFasta(fastaText, rowsPerFile);

    fastaChunks.forEach((chunk, i) => {
      zip.file(
        `query_part${i + 1}.fasta`,
        chunk.join("\n")
      );
    });


    const blob = await zip.generateAsync({ type: "blob" });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "validated_taxon_files.zip";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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

      {validated && (
        <div style={{ marginTop: '20px' }}>
          <div style={{ color: 'green', marginTop: '20px' }}>
          ✔ Validation Passed
          </div>

          {showDownloadWarning && (
            <div
              style={{
                background: "#fff3cd",
                color: "#856404",
                padding: "10px",
                border: "1px solid #ffeeba",
                borderRadius: "4px",
                marginBottom: "10px"
              }}
            >
              ⚠ <strong>Important:</strong> The uploaded files were 
              corrected during validation. Please download and use the validated CSV
              and FASTA files for future use.
            </div>
          )}
          
          <button
            onClick={() => downloadCsvAsZip(csvText, 150)}
          >
            Download validated CSVs and FASTAs (ZIP)
          </button>
        </div>
      )}

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
