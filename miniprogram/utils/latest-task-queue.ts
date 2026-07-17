export type TaskErrorHandler<T> = (error: unknown, task: T) => void;

interface QueuedTask<T> {
  sequence: number;
  task: T;
}

interface FlushWaiter {
  targetSequence: number;
  resolve: () => void;
  reject: (error: unknown) => void;
}

/**
 * Serializes asynchronous work while retaining only the newest task that has
 * not started yet. This is useful for autosave: intermediate snapshots may be
 * dropped, but an older request can never finish after a newer request.
 *
 * Background enqueue failures are reported through onError. flush additionally
 * rejects when the newest snapshot it is waiting for cannot be persisted, so a
 * caller can stop navigation instead of silently discarding local state.
 */
export class LatestTaskQueue<T> {
  private pending: QueuedTask<T> | null = null;
  private running = false;
  private issuedSequence = 0;
  private lastSettledSequence = 0;
  private lastSuccessfulSequence = 0;
  private lastError: { sequence: number; error: unknown } | null = null;
  private waiters: FlushWaiter[] = [];

  constructor(
    private readonly worker: (task: T) => Promise<void>,
    private readonly onError?: TaskErrorHandler<T>,
  ) {}

  enqueue(task: T): void {
    this.setPending(task);
    this.ensureDrain();
  }

  flush(task?: T): Promise<void> {
    const targetSequence = task !== undefined
      ? this.setPending(task)
      : this.issuedSequence;

    if (targetSequence === 0 || this.lastSuccessfulSequence >= targetSequence) {
      return Promise.resolve();
    }

    this.ensureDrain();
    return new Promise<void>((resolve, reject) => {
      this.waiters.push({ targetSequence, resolve, reject });
      this.settleWaiters();
    });
  }

  private setPending(task: T): number {
    const sequence = ++this.issuedSequence;
    this.pending = { sequence, task };
    return sequence;
  }

  private ensureDrain(): void {
    if (this.running || !this.pending) return;
    this.running = true;
    void this.drain();
  }

  private async drain(): Promise<void> {
    while (this.pending) {
      const queued = this.pending;
      this.pending = null;
      try {
        await this.worker(queued.task);
        this.lastSuccessfulSequence = queued.sequence;
      } catch (error) {
        this.lastError = { sequence: queued.sequence, error };
        try {
          this.onError?.(error, queued.task);
        } catch (_) {
          // Error reporting must never break the queue or strand flush callers.
        }
      }
      this.lastSettledSequence = queued.sequence;
    }

    this.running = false;
    if (this.pending) {
      this.ensureDrain();
      return;
    }
    this.settleWaiters();
  }

  private settleWaiters(): void {
    if (!this.waiters.length) return;
    const remaining: FlushWaiter[] = [];
    for (const waiter of this.waiters) {
      if (this.lastSuccessfulSequence >= waiter.targetSequence) {
        waiter.resolve();
      } else if (
        !this.running &&
        !this.pending &&
        this.lastSettledSequence >= waiter.targetSequence
      ) {
        waiter.reject(this.lastError?.error || new Error("任务执行失败"));
      } else {
        remaining.push(waiter);
      }
    }
    this.waiters = remaining;
  }
}
