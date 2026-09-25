const nodeUrlInput = document.getElementById('nodeUrl');
const refreshBtn = document.getElementById('refreshBtn');
const nodeStatus = document.getElementById('nodeStatus');
const addressesList = document.getElementById('addressesList');
const peersList = document.getElementById('peersList');
const mempoolList = document.getElementById('mempoolList');
const blocksList = document.getElementById('blocksList');

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function renderStatus(data) {
  if (!data) {
    nodeStatus.textContent = 'No data';
    return;
  }

  const info = [
    ['Port', data.port],
    ['Blocks', data.blocks?.length ?? 0],
    ['Peers', (data.peers || []).length],
    ['Last hash', data.last_hash || 'n/a'],
  ];

  nodeStatus.innerHTML = `
    <div class="meta">
      ${info
        .map(
          ([label, value]) => `
            <div>
              <strong>${label}</strong><br />
              <span>${value}</span>
            </div>
          `
        )
        .join('')}
    </div>
  `;
}

function renderAddresses(addresses) {
  if (!addresses || !addresses.length) {
    addressesList.textContent = 'No addresses found';
    addressesList.classList.add('empty');
    return;
  }

  addressesList.classList.remove('empty');
  addressesList.innerHTML = addresses
    .map((address) => `<span class="address-chip">${address}</span>`)
    .join('');
}

function renderPeers(peers) {
  if (!peers || !peers.length) {
    peersList.textContent = 'No peers';
    peersList.classList.add('empty');
    return;
  }

  peersList.classList.remove('empty');
  peersList.innerHTML = peers
    .map((peer) => `<span class="peer-chip">${peer}</span>`)
    .join('');
}

function renderMempool(mempool) {
  if (!mempool || !mempool.length) {
    mempoolList.textContent = 'Mempool is empty';
    mempoolList.classList.add('empty');
    return;
  }

  mempoolList.classList.remove('empty');
  mempoolList.innerHTML = mempool
    .map(
      (tx) => `
        <div class="tx">
          <div><strong>From:</strong> ${tx.sender || 'n/a'}</div>
          <div><strong>To:</strong> ${tx.recipient || 'n/a'}</div>
          <div><strong>Amount:</strong> ${tx.amount ?? 'n/a'}</div>
          <div><strong>Fee:</strong> ${tx.fee ?? 'n/a'}</div>
          <div><strong>Nonce:</strong> ${tx.nonce ?? 'n/a'}</div>
          <div><strong>Signature:</strong> ${tx.signature ? tx.signature.slice(0, 20) + '...' : 'n/a'}</div>
        </div>
      `
    )
    .join('');
}

function renderBlocks(blocks) {
  if (!blocks || !blocks.length) {
    blocksList.textContent = 'No blocks';
    blocksList.classList.add('empty');
    return;
  }

  blocksList.classList.remove('empty');
  blocksList.innerHTML = blocks
    .slice()
    .reverse()
    .map(
      (block) => `
        <div class="block-card">
          <div class="block-header">
            <span>Block #${block.index}</span>
            <span>${block.hash.slice(0, 12)}...</span>
          </div>
          <div class="meta">
            <div><strong>Prev</strong><br />${block.previous_hash.slice(0, 12)}...</div>
            <div><strong>Difficulty</strong><br />${block.difficulty}</div>
            <div><strong>Timestamp</strong><br />${block.timestamp}</div>
            <div><strong>Nonce</strong><br />${block.nonce}</div>
          </div>
          <div class="tx-list">
            ${(block.transactions || [])
              .map(
                (tx) => `
                  <div class="tx">
                    <div><strong>From:</strong> ${tx.sender}</div>
                    <div><strong>To:</strong> ${tx.recipient}</div>
                    <div><strong>Amount:</strong> ${tx.amount}</div>
                    <div><strong>Fee:</strong> ${tx.fee}</div>
                    <div><strong>Nonce:</strong> ${tx.nonce}</div>
                  </div>
                `
              )
              .join('') || '<div class="tx">No transactions</div>'}
          </div>
        </div>
      `
    )
    .join('');
}

async function loadData() {
  const nodeUrl = nodeUrlInput.value.trim();
  if (!nodeUrl) {
    nodeStatus.textContent = 'Please provide a node URL';
    return;
  }

  try {
    const status = await fetchJson(`${nodeUrl}/status`);
    const { addresses } = await fetchJson(`${nodeUrl}/addresses`);
    renderStatus(status);
    renderPeers(status.peers || []);
    renderMempool(status.mempool || []);
    renderBlocks(status.blocks || []);
    renderAddresses(addresses || []);
  } catch (error) {
    nodeStatus.textContent = `Failed to load data: ${error.message}`;
    addressesList.textContent = 'Unavailable';
    peersList.textContent = 'Unavailable';
    mempoolList.textContent = 'Unavailable';
    blocksList.textContent = 'Unavailable';
  }
}

refreshBtn.addEventListener('click', loadData);
loadData();
