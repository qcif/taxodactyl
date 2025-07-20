
const FULL_DATA_PATH = window.location.pathname.split("/").slice(0, -1).join("/") + "/"

async function saveReport(readonly = false) {

  $('#saveModal').modal('hide');
  $('body').removeClass('modal-open')
  $('body')[0].style = null
  $('.modal-backdrop').remove();

  // Clone the current document's HTML
  const clone = document.documentElement.cloneNode(true);
  if (readonly) {
    const saveModal = clone.querySelector('#saveModal');
    if (saveModal) saveModal.remove();
    const saveButton = clone.querySelector('#saveButton');
    if (saveButton) saveButton.remove();
  }

  // Update all input and textarea values
  const inputs = clone.querySelectorAll('input, textarea');
  inputs.forEach(input => {
    if (input.tagName === 'TEXTAREA') {
      input.textContent = input.value;
    } else if (input.type === 'text' || input.type === 'password') {
      input.setAttribute('value', input.value);
    } else if (input.type === 'checkbox' || input.type === 'radio') {
      if (input.checked) {
        input.setAttribute('checked', 'checked');
      } else {
        input.removeAttribute('checked');
      }
    }
    if (readonly) {
      input.readOnly = true;
    }
  });

  // Create a Blob with the modified HTML
  const doctype = '<!DOCTYPE html>';
  const htmlContent = doctype + '\n' + clone.outerHTML;

  try {
    const today = new Date().toISOString().split('T')[0];
    const handle = await window.showSaveFilePicker({
      suggestedName: `report_${SAMPLE_ID}_${today}.html`,
      types: [
        {
          description: 'HTML Files',
          accept: { 'text/html': ['.html'] }
        }
      ]
    });
    const writable = await handle.createWritable();
    await writable.write(htmlContent);
    await writable.close();
    console.log('File saved successfully');
  } catch (err) {
    console.error('Save canceled or failed:', err);
  }

}

function createSaveButton() {
  // Don't show the save button if the "save" modal is not present (readonly)
  if ($('#saveModal').length) {
    const saveButton = document.createElement('a');
    saveButton.classList.add('btn', 'btn-primary');
    saveButton.textContent = 'Save report';
    saveButton.style.position = 'fixed';
    saveButton.style.top = '1.5rem';
    saveButton.style.right = '1.5rem';
    saveButton.href = '#';
    saveButton.id = 'saveButton';
    saveButton.setAttribute('data-bs-toggle', 'modal');
    saveButton.setAttribute('data-bs-target', '#saveModal');
    document.body.appendChild(saveButton);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  createSaveButton();
  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      $('#saveModal').modal('show');
    }
  });
});
