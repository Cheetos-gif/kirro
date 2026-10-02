import type { Metadata } from 'next';
import { Geist_Mono, Inter, Space_Grotesk } from 'next/font/google';
import { NuqsAdapter } from 'nuqs/adapters/next/app';

import './globals.css';

import { MotionProvider } from '@/components/motion';
import { QueryProvider, ThemeProvider } from '@/components/providers';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { Toaster } from '@/components/ui/sonner';
import { currentViewer } from '@/lib/auth/roles';
import { cn } from '@/lib/utils';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-display' });

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'KIRRO',
  description:
    'KIRRO books scarce slots: courts, screenings, passes. Contested slots go to a seeded fair draw; the rest sell first come, first served.',
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const viewer = await currentViewer();

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        'h-full',
        'antialiased',
        geistMono.variable,
        spaceGrotesk.variable,
        'font-sans',
        inter.variable
      )}
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryProvider>
            <NuqsAdapter>
              <MotionProvider>
                <SiteHeader viewer={viewer} />
                {children}
                <SiteFooter />
              </MotionProvider>
            </NuqsAdapter>
          </QueryProvider>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
