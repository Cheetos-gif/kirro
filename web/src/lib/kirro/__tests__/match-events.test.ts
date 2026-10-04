import { describe, expect, it } from 'vitest';

import { matchEventsInText, matchEventsInTranscript } from '@/lib/kirro/match-events';
import type { KirroEvent } from '@/lib/kirro/schemas';

function event(overrides: Partial<KirroEvent> & Pick<KirroEvent, 'event_id' | 'name'>): KirroEvent {
  return {
    aliases: [],
    generic_aliases: [],
    fulfilment: 'digital',
    organiser_id: 'org_seed',
    status: 'published',
    ...overrides,
  };
}

const badminton = event({
  event_id: 'ev_badminton',
  name: 'Society Badminton Court',
  aliases: ['badminton', 'shuttle'],
});
const movie = event({
  event_id: 'ev_movie',
  name: 'Opening Night Movie, Screen 2',
  aliases: ['movie', 'film', 'cinema'],
});
const events = [badminton, movie];

describe('matchEventsInText', () => {
  it('matches an alias regardless of case', () => {
    expect(matchEventsInText('I want the BADMINTON court', events)).toEqual([badminton]);
  });

  it('matches a generic alias', () => {
    expect(matchEventsInText('book me a shuttle slot', events)).toEqual([badminton]);
  });

  it('matches the full name', () => {
    expect(matchEventsInText('Opening Night Movie, Screen 2 please', events)).toEqual([movie]);
  });

  it('returns nothing for unrelated text', () => {
    expect(matchEventsInText('what is the weather tomorrow', events)).toEqual([]);
  });

  it('returns multiple events when several are mentioned', () => {
    expect(matchEventsInText('badminton or maybe a film', events)).toEqual([badminton, movie]);
  });

  it('ignores empty aliases rather than matching everything', () => {
    const odd = event({ event_id: 'ev_odd', name: 'Odd Event', aliases: ['', '   '] });
    expect(matchEventsInText('completely unrelated sentence', [odd])).toEqual([]);
  });
});

describe('matchEventsInTranscript', () => {
  it('keeps an event listed once mentioned, even if later lines do not repeat it', () => {
    expect(
      matchEventsInTranscript(['I want badminton', 'yes', 'saturday works', 'four of us'], events)
    ).toEqual([badminton]);
  });

  it('orders events by first mention', () => {
    expect(
      matchEventsInTranscript(['a film please', 'actually badminton', 'film again'], events)
    ).toEqual([movie, badminton]);
  });

  it('returns nothing for an empty transcript', () => {
    expect(matchEventsInTranscript([], events)).toEqual([]);
  });
});
