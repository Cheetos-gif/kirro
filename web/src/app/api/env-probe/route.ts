import { NextResponse } from 'next/server';

// TEMPORARY diagnostic: reports the non-secret runtime env the deployment actually sees.
export function GET() {
  return NextResponse.json({
    mock_api_url: process.env.MOCK_API_URL ?? null,
    mock_run_id: process.env.MOCK_RUN_ID ?? null,
    vercel_env: process.env.VERCEL_ENV ?? null,
  });
}
