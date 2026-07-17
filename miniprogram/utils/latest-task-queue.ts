export type TaskErrorHandler<T> = (error: unknown, task: T) => void;

/**
 * Serializes asynchronous work while retaining only the newest task that has
 * not started yet. This is useful for autosave: intermediate snapshots may be
 * dropped, but an older request can never finish after a newer request.
 */
export class LatestTaskQueue<T> {
  private pending: T | null = null;
  private draining: Promise<void> | null = null;

  constructor(
    private readonly worker: (task: T) => Promise<void>,
    private readonly onError?: TaskErrorHandler<T>,
  ) {}

  enqueue(task: T): void {
    this.pending = task;
    this.ensureDrain();
  }

  async flush(task?: T): Promise<void> {
    if (task !== undefined) this.pending = task;
    this.ensureDrain();
    while (this.draining) await this.draining;
  }

  private ensureDrain(): void {
    if (!this.draining && this.pending !== null) this.draining = this.drain();
  }

  private async drain(): Promise<void> {
    try {
      while (this.pending !== null) {
        const task = this.pending;
        this.pending = null;
        try {
          await this.worker(task);
        } catch (error) {
          this.onError?.(error, task);
        }
      }
    } finally {
      this.draining = null;
      this.ensureDrain();
    }
  }
}
