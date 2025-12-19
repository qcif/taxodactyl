import { useState, useEffect } from 'react';
import Papa from 'papaparse';

export default function CsvEditor({ csvText, errorRows, onChange }) {
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
    <div style={{ marginTop: 20 }}>
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            {header.map(col => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {header.map(col => (
                <td key={col}>
                  <input
                    value={row[col] ?? ''}
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
