/**
 * Fingerprint Store - IndexedDB persistence for fingerprints
 */

const DB_NAME = 'metamorph-fingerprints';
const DB_VERSION = 1;
const STORE_NAME = 'fingerprints';
const CONFIG_STORE = 'config';

let db = null;

export class FingerprintStore {
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => { db = request.result; resolve(); };
      request.onupgradeneeded = (event) => {
        const database = event.target.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          database.createObjectStore(STORE_NAME, { keyPath: 'platform' });
        }
        if (!database.objectStoreNames.contains(CONFIG_STORE)) {
          database.createObjectStore(CONFIG_STORE, { keyPath: 'key' });
        }
      };
    });
  }

  async getAll() {
    return this._getAllFromStore(STORE_NAME);
  }

  async get(platform) {
    return this._getFromStore(STORE_NAME, platform);
  }

  async getForUrl(url) {
    const all = await this.getAll();
    for (const fp of Object.values(all)) {
      if (fp.platform?.origins?.some(origin => this._matchOrigin(url, origin))) {
        return fp;
      }
    }
    return null;
  }

  _matchOrigin(url, origin) {
    if (origin.includes('*')) {
      const regex = new RegExp('^' + origin.replace(/\*/g, '.*') + '$');
      return regex.test(url);
    }
    return url.startsWith(origin);
  }

  async setActive(platform, fingerprintData) {
    const existing = await this.get(platform);
    const record = {
      platform,
      version: fingerprintData.fingerprint?.version,
      data: fingerprintData,
      status: 'active',
      updatedAt: Date.now(),
      previous: existing ? { version: existing.version, data: existing.data } : null,
    };
    return this._putToStore(STORE_NAME, record);
  }

  async getPrevious(platform) {
    const record = await this.get(platform);
    return record?.previous || null;
  }

  async getVersion(platform, version) {
    // Simplified - would need version history store
    const record = await this.get(platform);
    if (record?.previous?.version === version) return record.previous;
    return null;
  }

  async _getAllFromStore(storeName) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const request = store.getAll();
      request.onsuccess = () => {
        const result = {};
        for (const item of request.result) {
          result[item.platform] = item;
        }
        resolve(result);
      };
      request.onerror = () => reject(request.error);
    });
  }

  async _getFromStore(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async _putToStore(storeName, value) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.put(value);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async setConfig(key, value) {
    return this._putToStore(CONFIG_STORE, { key, value });
  }

  async getConfig(key) {
    const record = await this._getFromStore(CONFIG_STORE, key);
    return record?.value;
  }
}