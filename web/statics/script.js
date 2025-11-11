/*
  Cleaned and consolidated upload script.
  - Uses elements that exist in statics/index.html: uploadArea, fileInput, fileList, uploadBtn, result
  - Provides drag & drop, file list, remove, and upload behavior
*/

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const uploadBtn = document.getElementById('uploadBtn');
const result = document.getElementById('result');

let selectedFiles = [];

function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function showResult(message, type = 'info') {
  if (!result) return console.warn('result element not found');
  result.className = `result ${type}`;
  result.textContent = message;
  result.style.display = 'block';
  // hide after 4s
  setTimeout(() => { result.style.display = 'none'; }, 4000);
}

function clearResult() {
  if (!result) return;
  result.textContent = '';
  result.className = 'result';
  result.style.display = 'none';
}

function renderFileList() {
  fileList.innerHTML = '';
  if (selectedFiles.length === 0) {
    uploadBtn.disabled = true;
    return;
  }

  selectedFiles.forEach((file, idx) => {
    const row = document.createElement('div');
    row.className = 'file-item';
    row.innerHTML = `
      <span class="file-name">${file.name}</span>
      <span class="file-size">${formatFileSize(file.size)}</span>
      <button type="button" class="remove-btn" data-idx="${idx}">
        <svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="#ff4757"><path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z"/></svg>
      </button>
    `;
    fileList.appendChild(row);
  });

  // attach handlers for remove buttons
  fileList.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const i = parseInt(e.currentTarget.dataset.idx);
      selectedFiles.splice(i, 1);
      renderFileList();
    });
  });

  uploadBtn.disabled = selectedFiles.length === 0;
}

function addFilesFromList(fileListInput) {
  const files = Array.from(fileListInput).filter(f => f.name && f.name.toLowerCase().endsWith('.pdf'));
  if (files.length === 0) {
    showResult('PDFファイルを選択してください', 'error');
    return;
  }

  // dedupe by name+size
  files.forEach(f => {
    const exists = selectedFiles.some(s => s.name === f.name && s.size === f.size);
    if (!exists) selectedFiles.push(f);
  });

  renderFileList();
  clearResult();
}

// Drag & Drop handlers -- prevent default on document to avoid browser opening file
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  document.addEventListener(eventName, (e) => e.preventDefault(), false);
});

uploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', (e) => {
  uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  if (e.dataTransfer && e.dataTransfer.files) {
    addFilesFromList(e.dataTransfer.files);
  }
});

// file input
fileInput.addEventListener('change', (e) => {
  if (e.target && e.target.files) {
    addFilesFromList(e.target.files);
    // allow re-selecting same file
    fileInput.value = '';
  }
});

// upload
uploadBtn.addEventListener('click', async () => {
  if (selectedFiles.length === 0) {
    showResult('ファイルを選択してください', 'error');
    return;
  }

  uploadBtn.disabled = true;
  uploadBtn.textContent = 'アップロード中...';
  clearResult();

  const fd = new FormData();
  selectedFiles.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (res.ok && data) {
      showResult(data.message || 'アップロード完了', 'success');
      selectedFiles = [];
      renderFileList();
    } else {
      showResult(data?.message || `アップロード失敗: ${res.status}`, 'error');
    }
  } catch (err) {
    console.error(err);
    showResult('ネットワークエラーが発生しました', 'error');
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'アップロード';
  }
});

// initialize
renderFileList();