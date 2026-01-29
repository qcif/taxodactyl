import { useState } from 'react';
import JSZip from "jszip";
import Papa from "papaparse";
import CsvEditor from './components/CsvEditor';
// import './App.css';

const ERROR_COLUMN_MAP = {
  "metadata_missing_sample": "sample_id",
  "invalid_taxa_of_interest": "taxa_of_interest",
  "invalid_pmi": "preliminary_id",
  "invalid_country": "country",
  "invalid_locus": "locus",
};

function App() {
  const [metadataFile, setMetadataFile] = useState(null);
  const [fastaFile, setFastaFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [editedCsvText, setEditedCsvText] = useState(null);
  const [errors, setErrors] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [fastaText, setFastaText] = useState('');
  const [validated, setValidated] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [errorRows, setErrorRows] = useState([]);
  const [showDownloadWarning, setShowDownloadWarning] = useState(false);
  const [highlightColumns, setHighlightColumns] = useState([]);
  const MAX_SEQ_LIMIT = 149
  
  const handleValidate = async () => {
    if (!fastaFile) {
      alert("Please select FASTA file");
      return;
    }

    const formData = new FormData();
    if (editedCsvText) {
      formData.append("metadata_text", editedCsvText);
    } else if (metadataFile) {
      formData.append("metadata_csv", metadataFile);
    } else {
      alert("Please select a CSV file");
      return;
    }
    formData.append("query_fasta", fastaFile);

    setIsValidating(true);
    
    try{
      const res = await fetch("http://127.0.0.1:8000/validate", {
        method: "POST",
        body: formData
      });

      const data = await res.json();
      if (res.ok) {
        setValidated(true);
        setErrors(null);
        setErrorRows([]);
        setCsvText(data.metadata_csv || "");
        setFastaText(data.query_fasta || "");
        setHighlightColumns([]);
        setShowDownloadWarning(
          data.message?.toLowerCase().includes("auto-fixed")
        );
      } else {
        setErrors(data.error);
        setCsvText(data.metadata_csv || "");
        setEditedCsvText(data.metadata_csv);
        setErrorRows(data.rows || []);
        // Highlight column based on error type
        if (data.error && data.error.type in ERROR_COLUMN_MAP) {
          setHighlightColumns([ERROR_COLUMN_MAP[data.error.type]]);
        }
        else {
          setHighlightColumns([]); 
        }
      }
    } finally {
      setIsValidating(false);
    }
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

  const downloadCsvFastaAsZip = async (csvText, fastaText, rowsPerFile = MAX_SEQ_LIMIT) => {
    
    // Split CSV files and zip
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

    // Split FASTA file and zip
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

  const resetValidateInputs = () => {
    setMetadataFile(null);
    setFastaFile(null);
    setEditedCsvText(null);
    setErrors(null);
    setCsvText("");
    setFastaText("");
    setValidated(false);
    setErrorRows([]);
    setShowDownloadWarning(false);
    setHighlightColumns([]);
    setFileInputKey(prev => prev + 2);
  };

  const isInvalidRequiredColumns =
  errors?.type === "invalid_required_columns";

  const isFastaError =
    errors &&
    errors.type?.startsWith("invalid_fasta");



  return (
    <>
      {/* Navbar */}
      <nav className="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
        <div className="container">
          <a className="navbar-brand" href="#">
            DAFF Biosecurity workflows
          </a>
        </div>
      </nav>

      <div className="container mt-5 pt-5">
        <h4 className="mb-4">
          Taxodactyl Input Validation
        </h4>

        {(validated || errors) && (
          <div className="mb-3 text-start">
            <button
              className="btn btn-outline-secondary"
              onClick={resetValidateInputs}
            >
              <i className="fas fa-redo me-2"></i>
              Upload a new dataset
            </button>
          </div>
        )}

        {/* Upload section */}
        {!(validated || errors) && (
          <>
            <div className="mb-3">
              <label className="form-label fw-bold">Metadata CSV</label>
              <input
                key={fileInputKey}
                type="file"
                className="form-control"
                accept=".csv"
                onChange={e => setMetadataFile(e.target.files[0])}
              />
            </div>

            <div className="mb-3">
              <label className="form-label fw-bold">Query FASTA</label>
              <input
                key={fileInputKey + 1}
                type="file"
                className="form-control"
                accept=".fasta,.fa"
                onChange={e => setFastaFile(e.target.files[0])}
              />
            </div>
          </>
        )}

        {/* Success */}
        {validated && (
          <>
            <div className="alert alert-success">
              <i className="fas fa-check-circle me-2"></i>
              Validation passed
            </div>

            <p className="alert alert-info">
              Your files have been successfully validated and are ready for
              download. Please note that if you submitted a large number of
              samples, your data may have been split into multiple parts. If so,
              please submit these as separate Taxodactyl jobs to avoid hitting
              the "Maxiumum sequences per job" limit.
            </p>

            {showDownloadWarning && (
              <div className="alert alert-warning">
                <strong>Important:</strong> The uploaded files were
                auto-corrected during validation. Please download and
                use the validated files.
              </div>
            )}

            <div className="text-center">
              <button
                className="btn btn-success"
                onClick={() =>
                  downloadCsvFastaAsZip(csvText, fastaText, 150)
                }
              >
                <i className="fas fa-download me-2"></i>
                Download validated files
              </button>
            </div>
          </>
        )}

        {/* Errors */}
        {errors && (
          <div className="alert alert-danger mt-4">
            <h5>Validation errors</h5>
            <pre 
              className="mb-0"
              style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {errors.message}
            </pre>

            {isFastaError && (
              <p className="mt-2 mb-0">
                Please fix this manually in your FASTA file and re-upload it to continue
                validation.
              </p>
            )}

            {isInvalidRequiredColumns && (
              <p className="mt-2 mb-0">
                Please fix the invalid column headers in the table below to continue
                validation.
              </p>
            )}

            {!isFastaError && !isInvalidRequiredColumns && (
              <p className="mt-2 mb-0">
                You can fix these values directly in the table below to continue
                validating your data.
              </p>
            )}
          </div>
        )}

        {errors && !isFastaError && (
          <CsvEditor
            csvText={csvText}
            onSave={handleValidate}
            errorRows={errorRows}
            onChange={setEditedCsvText}
            highlightColumns={highlightColumns}
          />
        )}

        {!validated && !isFastaError && (
          <div className="my-5">
            <button
              className="btn btn-primary"
              onClick={handleValidate}
              disabled={isValidating}
            >
              {isValidating ? (
                <>
                  <span
                    className="spinner-border spinner-border-sm me-2"
                    role="status"
                    aria-hidden="true"
                  ></span>
                  {validated || errors ? "Continuing validation..." : "Validating..."}
                    </>
                  ) : (
                    <>
                      {validated || errors ? "Continue validation" : "Validate"}
                    </>
              )}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

export default App;
