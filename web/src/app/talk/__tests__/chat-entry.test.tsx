import type { ReceivedChatMessage } from '@livekit/components-react';
import { ChatEntry } from '@livekit/components-react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

/**
 * `ChatEntry` is LiveKit's own row component, and the talk page hands it an entry object built from
 * a transcription segment rather than a chat message. It only reads `message`, `timestamp` and
 * (when the name is not hidden) `from`, so a minimal object is enough — but "enough" is the
 * assumption under test, because a component that renders nothing would leave the transcript pane
 * empty while looking perfectly wired up.
 */
describe('ChatEntry with a transcription-shaped entry', () => {
  const entry = {
    id: 'me|seg-1',
    timestamp: Date.now(),
    message: 'Which date do you want for the tennis court booking?',
  } as unknown as ReceivedChatMessage;

  it('renders the message text', () => {
    render(<ChatEntry entry={entry} hideName />);
    expect(
      screen.getByText('Which date do you want for the tennis court booking?')
    ).toBeInTheDocument();
  });
});
