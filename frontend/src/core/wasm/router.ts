/* Copyright 2024 Marimo. All rights reserved. */
class URLPyodideRouter {
  getFilename(): string | null {
    return this.getSearchParam("filename");
  }
  setFilename(filename: string) {
    this.setSearchParam("filename", filename);
  }

  getCodeFromSearchParam(): string | null {
    return this.getSearchParam("code");
  }

  getCodeFromHash(): string | null {
    const hash = globalThis.location.hash;
    const prefix = "#code/";
    if (!hash.startsWith(prefix)) {
      return null;
    }
    return hash.slice(prefix.length);
  }

  setCodeForHash(code: string) {
    globalThis.location.hash = `#code/${code}`;
  }

  private setSearchParam(key: string, value: string) {
    const url = new URL(globalThis.location.href);
    url.searchParams.set(key, value);
    globalThis.history.replaceState({}, "", url.toString());
  }

  private getSearchParam(key: string): string | null {
    const url = new URL(globalThis.location.href);
    return url.searchParams.get(key);
  }
}

export const PyodideRouter = new URLPyodideRouter();
