import React, {useMemo} from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {body} from '../fonts';
import {Word} from '../types';

type Page = {words: Word[]; startMs: number; endMs: number};

// Group words into short pages (max 3 words, break on pauses and sentence ends).
const paginate = (words: Word[]): Page[] => {
	const pages: Page[] = [];
	let cur: Word[] = [];
	for (const w of words) {
		const prev = cur[cur.length - 1];
		if (prev && (cur.length >= 3 || w.startMs - prev.endMs > 350 || /[.?!]$/.test(prev.text))) {
			pages.push({words: cur, startMs: cur[0].startMs, endMs: prev.endMs});
			cur = [];
		}
		cur.push(w);
	}
	if (cur.length) pages.push({words: cur, startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs});
	return pages;
};

export const Captions: React.FC<{words: Word[]; accent: string}> = ({words, accent}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const pages = useMemo(() => paginate(words), [words]);
	const ms = (frame / fps) * 1000;
	const idx = pages.findIndex((p, i) => ms >= p.startMs && ms < (pages[i + 1]?.startMs ?? p.endMs + 400));
	if (idx === -1) return null;
	const page = pages[idx];
	const pop = spring({frame: frame - Math.round((page.startMs / 1000) * fps), fps, config: {damping: 12, stiffness: 220}});
	return (
		<AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: '30%'}}>
			<div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', padding: '0 7%', transform: `scale(${0.85 + 0.15 * pop})`}}>
				{page.words.map((w, i) => {
					const active = ms >= w.startMs && ms < (page.words[i + 1]?.startMs ?? page.endMs + 400);
					return (
						<span
							key={i}
							style={{
								fontFamily: body,
								fontWeight: 900,
								fontSize: width * 0.085,
								color: active ? accent : 'white',
								WebkitTextStroke: `${width * 0.006}px black`,
								paintOrder: 'stroke',
								textShadow: '0 6px 24px rgba(0,0,0,0.9)',
								transform: active ? 'scale(1.08)' : undefined,
								display: 'inline-block',
								margin: '0 0.14em',
							}}
						>
							{w.text.toUpperCase()}
						</span>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
