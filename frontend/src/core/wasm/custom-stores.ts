/* Copyright 2024 Marimo. All rights reserved. */
import type { FileStore } from './store';
import { notebookFileStore } from './store';
import { getAppConfig } from '../config/config';
import { Logger } from '@/utils/Logger';

/**
 * Create a file store from class name by looking up global classes
 */
function createFileStore(className: string): FileStore | null {
  const FileStoreClass = (window as any)[className];
  
  if (!FileStoreClass) {
    Logger.warn(`File store class "${className}" not found on window object`);
    Logger.warn('Define file store classes globally: window.MyFileStore = class MyFileStore { ... }');
    return null;
  }
  
  if (typeof FileStoreClass !== 'function') {
    Logger.error(`File store class "${className}" is not a constructor function`);
    return null;
  }
  
  try {
    return new FileStoreClass();
  } catch (error) {
    Logger.error(`Failed to create file store of class "${className}":`, error);
    return null;
  }
}

/**
 * Initialize custom file stores from app config
 * This should be called early in the WASM initialization process
 */
export function initializeCustomFileStores() {
  const appConfig = getAppConfig();
  
  if (!appConfig.file_stores || appConfig.file_stores.length === 0) {
    return;
  }
  
  Logger.log('🗄️ Initializing custom file stores...');
  
  // Create custom file stores and inject them at the beginning (highest priority)
  const customStores: FileStore[] = [];
  
  for (const className of appConfig.file_stores) {
    const store = createFileStore(className);
    if (store) {
      customStores.push(store);
      Logger.log(`✅ Created file store: ${className}`);
    }
  }
  
  // Inject custom stores at the beginning of the notebookFileStore
  // Insert in reverse order so first in config gets highest priority
  for (let i = customStores.length - 1; i >= 0; i--) {
    notebookFileStore.insert(0, customStores[i]);
  }
  
  if (customStores.length > 0) {
    Logger.log(`🗄️ Injected ${customStores.length} custom file store(s) into notebookFileStore`);
  }
}

// File store classes should be defined globally on the window object
// Example: window.PouchDBFileStore = class PouchDBFileStore { ... };
