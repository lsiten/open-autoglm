import { openDB } from 'idb'

const DB_NAME = 'autoglm-db'
const DB_VERSION = 2 // Increment version
const STORE_CONFIG = 'config'
const STORE_SESSIONS = 'sessions'
const STORE_MESSAGES = 'messages'
const STORE_ALIASES = 'device_aliases'

const dbPromise = openDB(DB_NAME, DB_VERSION, {
  upgrade(db, oldVersion, newVersion, transaction) {
    if (!db.objectStoreNames.contains(STORE_CONFIG)) {
      db.createObjectStore(STORE_CONFIG)
    }
    if (!db.objectStoreNames.contains(STORE_SESSIONS)) {
      db.createObjectStore(STORE_SESSIONS, { keyPath: 'id' })
    }
    if (!db.objectStoreNames.contains(STORE_MESSAGES)) {
      const store = db.createObjectStore(STORE_MESSAGES, { keyPath: 'id', autoIncrement: true })
      store.createIndex('sessionId', 'sessionId', { unique: false })
    } else {
        // Migration for existing messages if needed (v1 -> v2)
        // If we want to keep old messages, we might need to assign them to a default session?
        // For now, let's assume clear or just add index if missing.
        const store = transaction.objectStore(STORE_MESSAGES)
        if (!store.indexNames.contains('sessionId')) {
            store.createIndex('sessionId', 'sessionId', { unique: false })
        }
    }
    if (!db.objectStoreNames.contains(STORE_ALIASES)) {
      db.createObjectStore(STORE_ALIASES)
    }
  },
})

export const db = {
  // ... existing methods ...

  // --- Sessions ---
  async getSessions() {
    return (await dbPromise).getAll(STORE_SESSIONS)
  },

  async addSession(session: any) {
    const s = JSON.parse(JSON.stringify(session))
    return (await dbPromise).put(STORE_SESSIONS, s)
  },

  async updateSession(id: string, updates: any) {
    const db = await dbPromise
    const tx = db.transaction(STORE_SESSIONS, 'readwrite')
    const store = tx.objectStore(STORE_SESSIONS)
    const session = await store.get(id)
    if (!session) return
    const newSession = { ...session, ...updates }
    await store.put(newSession)
    await tx.done
  },

  async deleteSession(id: string) {
      const db = await dbPromise
      const tx = db.transaction([STORE_SESSIONS, STORE_MESSAGES], 'readwrite')
      await tx.objectStore(STORE_SESSIONS).delete(id)
      
      // Delete associated messages
      const msgStore = tx.objectStore(STORE_MESSAGES)
      const index = msgStore.index('sessionId')
      let cursor = await index.openCursor(IDBKeyRange.only(id))
      while (cursor) {
          await cursor.delete()
          cursor = await cursor.continue()
      }
      await tx.done
  },

  // --- Messages ---
  async getMessages(sessionId: string) {
    const db = await dbPromise
    // If sessionId is provided, use index
    if (sessionId) {
        return db.getAllFromIndex(STORE_MESSAGES, 'sessionId', sessionId)
    }
    return db.getAll(STORE_MESSAGES)
  },

  async addMessage(message: any) {
    // Clone to avoid reactivity issues if passed a reactive object
    const msg = JSON.parse(JSON.stringify(message))
    return (await dbPromise).add(STORE_MESSAGES, msg)
  },

  async updateMessage(id: number, updates: any) {
    const db = await dbPromise
    const tx = db.transaction(STORE_MESSAGES, 'readwrite')
    const store = tx.objectStore(STORE_MESSAGES)
    
    const msg = await store.get(id)
    if (!msg) return
    
    const plainUpdates = JSON.parse(JSON.stringify(updates))
    const newMsg = { ...msg, ...plainUpdates }
    await store.put(newMsg)
    await tx.done
  },
  
  async saveAllMessages(messages: any[]) {
      // Clear and replace? Or just append?
      // For simplicity in this session-based app, we might want to just dump the current state
      // But clearing and rewriting is inefficient.
      // Let's rely on add/update in the UI logic.
      // But if we want to "Snapshot" the history:
      const db = await dbPromise
      const tx = db.transaction(STORE_MESSAGES, 'readwrite')
      const store = tx.objectStore(STORE_MESSAGES)
      await store.clear()
      for (const msg of messages) {
          await store.add(msg)
      }
      await tx.done
  },

  async clearMessages() {
    return (await dbPromise).clear(STORE_MESSAGES)
  },

  // --- Config ---
  async getConfig() {
    return (await dbPromise).get(STORE_CONFIG, 'main')
  },

  async saveConfig(config: any) {
    const c = JSON.parse(JSON.stringify(config))
    return (await dbPromise).put(STORE_CONFIG, c, 'main')
  },

  // --- Device Aliases ---
  async getDeviceAliases() {
    const db = await dbPromise
    const keys = await db.getAllKeys(STORE_ALIASES)
    const values = await db.getAll(STORE_ALIASES)
    const aliases: Record<string, string> = {}
    keys.forEach((key, i) => {
        aliases[key as string] = values[i]
    })
    return aliases
  },

  async saveDeviceAlias(id: string, name: string) {
    return (await dbPromise).put(STORE_ALIASES, name, id)
  }
}
