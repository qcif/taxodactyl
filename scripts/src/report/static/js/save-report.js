
const FULL_DATA_PATH = window.location.pathname.split("/").slice(0, -1).join("/") + "/"

async function saveReport(readonly = false) {

  const saveModalEl = document.getElementById('saveModal');
  const saveModal = bootstrap.Modal.getOrCreateInstance(saveModalEl);
  saveModal.hide();

  // Clone the current document's HTML
  const clone = document.documentElement.cloneNode(true);

  // Strip transient Bootstrap modal state — hide() is animated, so the
  // backdrop and modal-open class may still be present at clone time.
  clone.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
  const clonedBody = clone.querySelector('body');
  if (clonedBody) {
    clonedBody.classList.remove('modal-open');
    clonedBody.style.removeProperty('padding-right');
  }
  clone.querySelectorAll('.modal').forEach(el => {
    el.classList.remove('show');
    el.removeAttribute('style');
    el.removeAttribute('aria-modal');
    el.setAttribute('aria-hidden', 'true');
  });

  if (readonly) {
    const saveModalClone = clone.querySelector('#saveModal');
    if (saveModalClone) saveModalClone.remove();
    const saveButtonClone = clone.querySelector('#saveButton');
    if (saveButtonClone) saveButtonClone.remove();
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
