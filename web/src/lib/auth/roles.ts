import { redirect } from 'next/navigation';

import { auth } from '@/auth';
import { adminEmails } from '@/env';
import { listOrganisers } from '@/lib/kirro/api';

export type Role = 'user' | 'organiser' | 'admin';

export interface Viewer {
  email: string;
  name?: string | null;
  image?: string | null;
  role: Role;
}

/**
 * Resolve the signed-in viewer and their role. Admin comes from the seeded email allowlist (never stored in the
 * mock); organiser comes from an approved organiser request whose `requested_by` matches the Google email. If the
 * mock is unreachable the caller still gets a viewer, as a plain user — a degraded read must not lock people out.
 */
export async function currentViewer(): Promise<Viewer | null> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) return null;

  let role: Role = adminEmails().includes(email.toLowerCase()) ? 'admin' : 'user';
  if (role === 'user') {
    try {
      const organisers = await listOrganisers();
      if (
        organisers.some(
          organiser =>
            organiser.status === 'approved' &&
            organiser.requested_by?.toLowerCase() === email.toLowerCase()
        )
      ) {
        role = 'organiser';
      }
    } catch {
      // Mock unreachable: view as a plain user rather than failing the whole page.
    }
  }

  return { email, name: session.user?.name, image: session.user?.image, role };
}

/** Signed-in viewer, or redirect to sign-in. */
export async function requireViewer(): Promise<Viewer> {
  const viewer = await currentViewer();
  if (!viewer) redirect('/signin');
  return viewer;
}

export async function requireRole(role: Role): Promise<Viewer> {
  const viewer = await requireViewer();
  if (viewer.role !== role) redirect('/');
  return viewer;
}
