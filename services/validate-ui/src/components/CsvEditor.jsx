import { useState, useEffect } from 'react';
import Papa from 'papaparse';

export default function CsvEditor({ csvText, onSave, errorRows }) {
  const [rows, setRows] = useState([]);
  const [header, setHeader] = useState([]);
  const [fullRows, setFullRows] = useState([]);

  useEffect(() => {
    const parsed = Papa.parse(csvText, { header: true });
    setHeader(parsed.meta.fields || []);
    setFullRows(parsed.data);
    if (errorRows && errorRows.length > 0) {
      const filtered = parsed.data.filter((_, idx) =>
        errorRows.some(r => r._row_number === idx + 2) // backend row numbers start at 2
      );
      setRows(filtered);
    } else {
    setRows(parsed.data);
    }
  }, [csvText, errorRows]);

  const handleCellChange = (rowIndex, column, value) => {
    const newRows = [...rows];
    newRows[rowIndex][column] = value;
    setRows(newRows);
  };

  // const handleSave = () => {
  //   const csv = Papa.unparse(rows);
  //   onSave(csv);
  // };
  const handleSave = () => {
    let mergedRows = [...fullRows];
    rows.forEach(row => {
      const idx = mergedRows.findIndex(r => r._row_number === row._row_number);
      if (idx !== -1) mergedRows[idx] = row;
    });
    
    const csv = Papa.unparse({
      fields: header,
      data: rows
    });
    onSave(csv);
  };


  return (
    <div style={{ marginTop: '20px' }}>
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            {header.map(col => <th key={col}>{col}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {header.map(col => (
                <td key={col}>
                  <input
                    value={row[col]}
                    onChange={e => handleCellChange(i, col, e.target.value)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={handleSave} style={{ marginTop: '10px' }}>Save & Revalidate</button>
    </div>
  );
}
