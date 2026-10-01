import { NextResponse } from 'next/server';

import { auth } from '@/auth';

export default auth(req => {
  if (!req.auth) {
    const signInUrl = new URL('/api/auth/signin', req.nextUrl.origin);
    signInUrl.searchParams.set('callbackUrl', req.nextUrl.pathname);
    return NextResponse.redirect(signInUrl);
  }
});

export const config = {
  matcher: ['/dashboard/:path*'],
};
