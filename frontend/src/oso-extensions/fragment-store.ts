import { compressToEncodedURIComponent, decompressFromEncodedURIComponent } from "lz-string";

// Implements storing things in the fragment identifier
export class FragmentStore {
    private params: URLSearchParams;

    public static load() {
        return new FragmentStore(new URLSearchParams(window.location.hash));
    }

    constructor(searchParams: URLSearchParams) {
        this.params = searchParams;
    }

    getString(key: string): string | null {
        const value = this.params.get(key);
        if (!value) return null;
        return decompressFromEncodedURIComponent(value);
    }

    getJSON<T>(key: string): T | null {
        const value = this.getString(key);
        if (!value) return null;
        try {
            return JSON.parse(value) as T;
        } catch {
            return null;
        }
    }

    setString(key: string, value: string): void {
        this.params.set(key, compressToEncodedURIComponent(value));
    }

    setJSON<T>(key: string, value: T): void {
        this.setString(key, JSON.stringify(value));
    }

    commit(): void {
        const hash = this.params.toString();
        window.location.hash = hash;
    }
}
