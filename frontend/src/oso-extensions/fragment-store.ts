import { compressToEncodedURIComponent, decompressFromEncodedURIComponent } from "lz-string";

// Implements storing things in the fragment identifier
export class FragmentStore {
    private params: URLSearchParams;

    public static load() {
        return new FragmentStore(new URLSearchParams(window.location.hash.slice(1)));
    }

    constructor(searchParams: URLSearchParams) {
        this.params = searchParams;
    }

    getString(key: string): string | null {
        const value = this.params.get(key);
        if (!value) return null;
        return (value);
    }

    getCompressedString(key: string): string | null {
        const value = this.params.get(key);
        if (!value) return null;
        return decompressFromEncodedURIComponent(value);
    }

    getJSON<T>(key: string): T | null {
        const value = this.getCompressedString(key);
        if (!value) {
            return null;
        }
        try {
            return JSON.parse(value) as T;
        } catch {
            return null;
        }
    }

    setString(key: string, value: string): void {
        this.params.set(key, value);
    }

    setCompressedString(key: string, value: string): void {
        this.params.set(key, compressToEncodedURIComponent(value));
    }

    setJSON<T>(key: string, value: T): void {
        this.setCompressedString(key, JSON.stringify(value));
    }

    delete(key: string): void {
        this.params.delete(key);
    }

    commit(): void {
        const hash = this.params.toString();
        window.location.hash = hash;
    }
}
