/* Copyright 2024 Marimo. All rights reserved. */
class URLPyodideRouter {
  getFilename(): string | null {
    return this.getSearchParam("filename");
  }
  setFilename(filename: string) {
    this.setSearchParam("filename", filename);
  }

  getCode(): string | null {
    return this.getSearchParam("code");
  }

  private setSearchParam(key: string, value: string) {
    const url = new URL(window.location.href);
    url.searchParams.set(key, value);
    window.history.replaceState({}, "", url.toString());
  }

  private getSearchParam(key: string): string | null {
    const url = new URL(window.location.href);
    return url.searchParams.get(key);
  }
}

export const PyodideRouter = new URLPyodideRouter();
