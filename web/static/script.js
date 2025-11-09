// Client-side upload script for the invoice uploader with drag & drop and multiple files
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const uploadBtn = document.getElementById('uploadBtn');
const clearBtn = document.getElementById('clearBtn');
const controls = document.getElementById('controls');
const msg = document.getElementById('message');

let selectedFiles = [];

// ファイルサイズをフォーマット
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// メッセージ表示
function showMessage(text, type = 'info') {
  msg.textContent = text;
  msg.className = type;
}

function hideMessage() {
  msg.className = '';
  msg.style.display = 'none';
}

// ファイルリストを更新
function updateFileList() {
  fileList.innerHTML = '';
  
  if (selectedFiles.length === 0) {
    controls.style.display = 'none';
    hideMessage();
    return;
  }

  controls.style.display = 'flex';
  
  selectedFiles.forEach((file, index) => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="file-info">
        <div class="file-icon">PDF</div>
        <div class="file-details">
          <p class="file-name">${file.name}</p>
          <p class="file-size">${formatFileSize(file.size)}</p>
        </div>
      </div>
      <button class="file-remove" data-index="${index}" title="削除">×</button>
    `;
    fileList.appendChild(item);
  });

  // 削除ボタンのイベント
  document.querySelectorAll('.file-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const index = parseInt(e.target.dataset.index);
      selectedFiles.splice(index, 1);
      updateFileList();
    });
  });
}

// ファイル追加（重複チェック付き）
function addFiles(files) {
  const pdfFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
  
  if (pdfFiles.length === 0) {
    showMessage('PDFファイルを選択してください', 'error');
    return;
  }

  // 重複チェック（ファイル名とサイズで判定）
  pdfFiles.forEach(file => {
    const isDuplicate = selectedFiles.some(
      f => f.name === file.name && f.size === file.size
    );
    if (!isDuplicate) {
      selectedFiles.push(file);
    }
  });

  updateFileList();
  hideMessage();
}

// ドラッグ&ドロップイベント
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles(e.dataTransfer.files);
});

// ファイル選択
fileInput.addEventListener('change', (e) => {
  addFiles(e.target.files);
  fileInput.value = ''; // 同じファイルを再選択可能にする
});

// クリアボタン
clearBtn.addEventListener('click', () => {
  selectedFiles = [];
  updateFileList();
  fileInput.value = '';
  hideMessage();
});

// アップロードボタン
uploadBtn.addEventListener('click', async () => {
  if (selectedFiles.length === 0) {
    showMessage('ファイルを選択してください', 'error');
    return;
  }

  uploadBtn.disabled = true;
  clearBtn.disabled = true;
  showMessage(`${selectedFiles.length}個のファイルをアップロード中...`, 'info');

  const formData = new FormData();
  selectedFiles.forEach(file => {
    formData.append('files', file);
  });

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();
    
    if (res.ok) {
      showMessage(data.message || 'アップロード完了', 'success');
      selectedFiles = [];
      updateFileList();
      fileInput.value = '';
    } else {
      showMessage(data.message || `エラー: ${res.status}`, 'error');
    }
  } catch (e) {
    console.error(e);
    showMessage('ネットワークエラーが発生しました', 'error');
  } finally {
    uploadBtn.disabled = false;
    clearBtn.disabled = false;
  }
});