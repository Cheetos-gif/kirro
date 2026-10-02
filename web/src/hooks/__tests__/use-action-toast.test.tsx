import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useActionToast } from '../use-action-toast';

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('sonner', () => ({ toast }));

describe('useActionToast', () => {
  beforeEach(() => {
    toast.success.mockClear();
    toast.error.mockClear();
  });

  it('stays quiet until a result arrives', () => {
    renderHook(() => useActionToast(null));
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('shows a success toast for an ok result', () => {
    renderHook(() => useActionToast({ ok: true, message: 'Booked. Reference BK-0001.' }));
    expect(toast.success).toHaveBeenCalledWith('Booked. Reference BK-0001.');
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('shows an error toast for a failed result', () => {
    renderHook(() => useActionToast({ ok: false, message: 'Not enough seats left.' }));
    expect(toast.error).toHaveBeenCalledWith('Not enough seats left.');
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('does not repeat a toast when the same result re-renders', () => {
    const state = { ok: true, message: 'You are in the draw.' };
    const { rerender } = renderHook(({ value }) => useActionToast(value), {
      initialProps: { value: state as typeof state | null },
    });
    rerender({ value: state });
    expect(toast.success).toHaveBeenCalledTimes(1);
  });
});
