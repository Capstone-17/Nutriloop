import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { dbManager } from "../db/database";

const DISCLAIMER_ACCEPTED_KEY = "nutriloop_disclaimer_accepted";

/**
 * Hardware-backed secure storage service using expo-secure-store
 * with graceful fallback to SQLite / memory for environments without Keystore/Keychain.
 */
export class SecureStorageService {
  private static async isSecureStoreAvailable(): Promise<boolean> {
    if (Platform.OS === "web") return false;
    try {
      return await SecureStore.isAvailableAsync();
    } catch {
      return false;
    }
  }

  /**
   * Save a key-value pair securely.
   */
  static async setItem(key: string, value: string): Promise<void> {
    try {
      const available = await this.isSecureStoreAvailable();
      if (available) {
        await SecureStore.setItemAsync(key, value, {
          keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        });
        return;
      }
    } catch (e) {
      console.warn(`SecureStore write failed for "${key}", falling back:`, e);
    }
    // Fallback to SQLite app_settings
    try {
      await dbManager.saveSetting(`sec_${key}`, value);
    } catch (err) {
      console.warn(`Fallback storage write failed for "${key}":`, err);
    }
  }

  /**
   * Retrieve a key-value pair securely.
   */
  static async getItem(key: string): Promise<string | null> {
    try {
      const available = await this.isSecureStoreAvailable();
      if (available) {
        const val = await SecureStore.getItemAsync(key);
        if (val !== null) return val;
      }
    } catch (e) {
      console.warn(`SecureStore read failed for "${key}", falling back:`, e);
    }
    // Fallback to SQLite app_settings
    try {
      return await dbManager.getSetting(`sec_${key}`);
    } catch {
      return null;
    }
  }

  /**
   * Delete a key-value pair securely.
   */
  static async deleteItem(key: string): Promise<void> {
    try {
      const available = await this.isSecureStoreAvailable();
      if (available) {
        await SecureStore.deleteItemAsync(key);
      }
    } catch {
      // Ignore
    }
    try {
      await dbManager.saveSetting(`sec_${key}`, "");
    } catch {
      // Ignore
    }
  }

  /**
   * Check if user has accepted the mandatory Medical & Clinical Intelligence Disclaimer.
   */
  static async isDisclaimerAccepted(): Promise<boolean> {
    const val = await this.getItem(DISCLAIMER_ACCEPTED_KEY);
    return val === "true" || val === "1";
  }

  /**
   * Persist user acceptance of the Medical & Clinical Intelligence Disclaimer.
   */
  static async setDisclaimerAccepted(accepted: boolean = true): Promise<void> {
    await this.setItem(DISCLAIMER_ACCEPTED_KEY, accepted ? "true" : "false");
  }
}
