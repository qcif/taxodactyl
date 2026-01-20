import { useState, useEffect } from 'react';
import Papa from 'papaparse';

export default function CsvEditor({ csvText, errorRows, onChange, highlightColumns = [] }) {
  const [rows, setRows] = useState([]);
  const [header, setHeader] = useState([]);
  const [fullRows, setFullRows] = useState([]);

  useEffect(() => {
    const parsed = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true
    });

    setHeader(parsed.meta.fields || []);
    setFullRows(parsed.data);

    if (errorRows && errorRows.length > 0) {
      const filtered = parsed.data.filter((_, idx) =>
        errorRows.includes(idx)
      );
      setRows(filtered);
    } else {
      setRows(parsed.data);
    }
  }, [csvText, errorRows]);

  const handleHeaderChange = (oldName, newName) => {
    if (!newName || newName === oldName) return;

    const newHeader = header.map(h =>
      h === oldName ? newName : h
    );
    setHeader(newHeader);

    const rebuiltRows = fullRows.map(row => {
      const newRow = {};
      newHeader.forEach(col => {
        if (col === newName) {
          newRow[col] = row[oldName];
        } else {
          newRow[col] = row[col];
        }
      });
      return newRow;
    });

    setFullRows(rebuiltRows);

    const newCsvText = Papa.unparse({
      fields: newHeader,
      data: rebuiltRows
    });

    onChange(newCsvText);
  };


  const handleCellChange = (rowIndex, column, value) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex] = {
      ...updatedRows[rowIndex],
      [column]: value
    };
    setRows(updatedRows);

    // merge edits back into full CSV immediately
    const merged = [...fullRows];
    errorRows.forEach((csvIdx, i) => {
      merged[csvIdx] = updatedRows[i];
    });

    const newCsvText = Papa.unparse(merged);
    onChange(newCsvText); // push edited CSV up
  };

  if (!rows.length) return null;

  return (
    <div className="mt-4">
      <table className="table table-sm table-bordered table-full">
        <thead className="thead-light">
          <tr>
            {header.map(col => (
              <th key={col}>
                <input
                  className={`form-control form-control-sm font-weight-bold ${
                    highlightColumns.includes(col) ? 'bg-warning' : ''
                  }`}
                  value={col}
                  onChange={e =>
                    handleHeaderChange(col, e.target.value.trim())
                  }
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {header.map(col => (
                <td
                  key={col}
                  className={
                    highlightColumns.includes(col)
                      ? "bg-warning"
                      : ""
                  }
                >
                  <textarea
                    className={`form-control form-control-sm ${
                      highlightColumns.includes(col) ? 'is-invalid' : ''
                    }`}
                    value={row[col] ?? ""}
                    onChange={e =>
                      handleCellChange(i, col, e.target.value)
                    }
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
