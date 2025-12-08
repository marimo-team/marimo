/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Spatial hash grid for efficient collision detection
 * Provides O(n) collision detection instead of O(n²) by only checking nearby nodes
 */

export interface SpatialBounds {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export class SpatialHash {
  private grid: Map<string, SpatialBounds[]>;
  private cellSize: number;

  constructor(cellSize: number = 200) {
    this.grid = new Map();
    this.cellSize = cellSize;
  }

  /**
   * Get grid cell key for a position
   */
  private getKey(x: number, y: number): string {
    const cellX = Math.floor(x / this.cellSize);
    const cellY = Math.floor(y / this.cellSize);
    return `${cellX},${cellY}`;
  }

  /**
   * Get all grid cells that a bounds object overlaps
   */
  private getCells(bounds: SpatialBounds): string[] {
    const cells: string[] = [];

    const minX = Math.floor(bounds.x / this.cellSize);
    const maxX = Math.floor((bounds.x + bounds.width) / this.cellSize);
    const minY = Math.floor(bounds.y / this.cellSize);
    const maxY = Math.floor((bounds.y + bounds.height) / this.cellSize);

    for (let x = minX; x <= maxX; x++) {
      for (let y = minY; y <= maxY; y++) {
        cells.push(`${x},${y}`);
      }
    }

    return cells;
  }

  /**
   * Insert a bounds object into the spatial hash
   */
  insert(bounds: SpatialBounds): void {
    const cells = this.getCells(bounds);

    for (const cell of cells) {
      if (!this.grid.has(cell)) {
        this.grid.set(cell, []);
      }
      this.grid.get(cell)!.push(bounds);
    }
  }

  /**
   * Get all bounds objects that could potentially collide with the given bounds
   * Returns objects in nearby grid cells
   */
  getNearby(bounds: SpatialBounds): SpatialBounds[] {
    const cells = this.getCells(bounds);
    const nearby = new Set<SpatialBounds>();

    for (const cell of cells) {
      const cellBounds = this.grid.get(cell);
      if (cellBounds) {
        for (const other of cellBounds) {
          // Don't include the object itself
          if (other.id !== bounds.id) {
            nearby.add(other);
          }
        }
      }
    }

    return Array.from(nearby);
  }

  /**
   * Clear the spatial hash
   */
  clear(): void {
    this.grid.clear();
  }

  /**
   * Get debug statistics about the spatial hash
   */
  getStats(): {
    totalCells: number;
    totalObjects: number;
    avgObjectsPerCell: number;
  } {
    const totalCells = this.grid.size;
    let totalObjects = 0;

    for (const cell of this.grid.values()) {
      totalObjects += cell.length;
    }

    return {
      totalCells,
      totalObjects,
      avgObjectsPerCell: totalCells > 0 ? totalObjects / totalCells : 0,
    };
  }
}
