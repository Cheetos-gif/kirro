import { format, parseISO } from 'date-fns';

/** Paise (the mock's unit everywhere) to a rupee string. 25000 -> "₹250". */
export function formatPaise(paise: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

export function formatDateTime(iso: string): string {
  return format(parseISO(iso), 'EEE d MMM, HH:mm');
}

export function formatDate(iso: string): string {
  return format(parseISO(iso), 'EEE d MMM yyyy');
}
