import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { SiteHeader } from '@/components/site-header';
import type { Viewer } from '@/lib/auth/roles';

vi.mock('next-auth/react', () => ({ signIn: vi.fn(), signOut: vi.fn() }));

const viewer: Viewer = { email: 'org@example.com', role: 'organiser' };

describe('SiteHeader mobile nav', () => {
  it('opens a drawer with the signed-in viewer\'s links behind the menu trigger', async () => {
    render(<SiteHeader viewer={viewer} />);

    // The desktop nav (CSS-hidden, not DOM-removed, at this width in jsdom) already renders these
    // same links, so assertions below are scoped to the drawer's own dialog, not the page at large.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const drawer = within(await screen.findByRole('dialog'));
    expect(drawer.getByRole('link', { name: 'My events' })).toBeInTheDocument();
    expect(drawer.getByRole('link', { name: 'My bookings' })).toBeInTheDocument();
    expect(drawer.getByText('org@example.com')).toBeInTheDocument();
    expect(drawer.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });

  it('closes the drawer after following a link', async () => {
    render(<SiteHeader viewer={viewer} />);

    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    const drawer = within(await screen.findByRole('dialog'));
    await userEvent.click(drawer.getByRole('link', { name: 'My bookings' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows no sign-out control in the drawer for a signed-out viewer', async () => {
    render(<SiteHeader viewer={null} />);

    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const drawer = within(await screen.findByRole('dialog'));
    expect(drawer.getByRole('link', { name: 'Listings' })).toBeInTheDocument();
    expect(drawer.queryByRole('link', { name: 'My bookings' })).not.toBeInTheDocument();
    expect(drawer.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  });
});
