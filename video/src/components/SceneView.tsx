import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {body, display} from '../fonts';
import {Scene} from '../types';
import {Shots} from './Shots';

// Big kinetic text: words land one by one, last word in the accent colour.
const KineticText: React.FC<{text: string; accent: string}> = ({text, accent}) => {
	const frame = useCurrentFrame();
	const {fps, width, height} = useVideoConfig();
	const words = text.toUpperCase().split(/\s+/).filter(Boolean);
	const size = Math.min(width, height) * (words.length <= 3 ? 0.17 : 0.11);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: '0 8%'}}>
			<div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center'}}>
				{words.map((w, i) => {
					const s = spring({frame: frame - i * 5, fps, config: {damping: 14, stiffness: 180}});
					return (
						<span
							key={i}
							style={{
								fontFamily: display,
								fontSize: size,
								lineHeight: 1.05,
								color: i === words.length - 1 ? accent : 'white',
								transform: `translateY(${(1 - s) * 60}px) scale(${0.8 + 0.2 * s})`,
								opacity: s,
								textShadow: '0 8px 40px rgba(0,0,0,0.8)',
								margin: '0 0.12em',
								display: 'inline-block',
							}}
						>
							{w}
						</span>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

const Quote: React.FC<{text: string; person?: string; accent: string}> = ({text, person, accent}) => {
	const frame = useCurrentFrame();
	const {width, height, durationInFrames} = useVideoConfig();
	const portrait = height > width;
	const chars = Math.round(interpolate(frame, [5, Math.min(durationInFrames * 0.6, 5 + text.length * 1.2)], [0, text.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
	const size = Math.min(width, height) * (portrait ? 0.065 : 0.05);
	return (
		<AbsoluteFill style={{justifyContent: 'center', padding: portrait ? '0 9%' : '0 14%'}}>
			<div style={{fontFamily: display, fontSize: size * 3, color: accent, lineHeight: 0.6}}>“</div>
			<div style={{fontFamily: body, fontWeight: 800, fontSize: size, color: 'white', lineHeight: 1.3, textShadow: '0 4px 30px #000'}}>
				{text.slice(0, chars)}
			</div>
			{person ? (
				<div style={{fontFamily: body, fontWeight: 600, fontSize: size * 0.55, color: accent, marginTop: size * 0.6, letterSpacing: 2}}>
					— {person.toUpperCase()}
				</div>
			) : null}
		</AbsoluteFill>
	);
};

const ChapterCard: React.FC<{index: number; title: string; label: string; accent: string}> = ({index, title, label, accent}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const inS = spring({frame, fps, config: {damping: 200}});
	const out = interpolate(frame, [70, 85], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{justifyContent: 'center', paddingLeft: '7%', opacity: out, background: `linear-gradient(90deg, rgba(0,0,0,${0.75 * inS}) 0%, transparent 70%)`}}>
			<div style={{fontFamily: body, fontWeight: 800, fontSize: width * 0.016, color: accent, letterSpacing: 6, transform: `translateX(${(1 - inS) * -80}px)`}}>
				{label} {index}
			</div>
			<div style={{height: 6, width: width * 0.08 * inS, background: accent, margin: '14px 0 18px'}} />
			<div style={{fontFamily: display, fontSize: width * 0.055, color: 'white', lineHeight: 1, maxWidth: '60%', transform: `translateX(${(1 - inS) * -120}px)`}}>
				{title.toUpperCase()}
			</div>
		</AbsoluteFill>
	);
};

export const SceneView: React.FC<{scene: Scene; accent: string; chapterLabel: string}> = ({scene, accent, chapterLabel}) => {
	const textLike = scene.type === 'text' || scene.type === 'quote';
	return (
		<AbsoluteFill>
			<Shots shots={scene.shots} dim={textLike ? 0.62 : 0} />
			{scene.type === 'text' && scene.onscreen ? <KineticText text={scene.onscreen} accent={accent} /> : null}
			{scene.type === 'quote' && scene.onscreen ? <Quote text={scene.onscreen} person={scene.person} accent={accent} /> : null}
			{scene.chapter ? <ChapterCard index={scene.chapter.index} title={scene.chapter.title} label={chapterLabel} accent={accent} /> : null}
		</AbsoluteFill>
	);
};
