import {fitText} from '@remotion/layout-utils';
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, Img, staticFile} from 'remotion';
import {display, fontsReady} from './fonts';
import {ThumbnailProps} from './types';

// "NOBODY [person] BELIEVED" layout: words on the sides, cut-out in the middle,
// second person behind on the left in the accent colour, dark red glow.
const SideWord: React.FC<{text: string; side: 'left' | 'right'}> = ({text, side}) => {
	const {fontSize} = fitText({text: text.toUpperCase(), withinWidth: 330, fontFamily: display});
	return (
		<div
			style={{
				position: 'absolute',
				top: 0,
				bottom: 0,
				[side]: 26,
				width: 330,
				display: 'flex',
				alignItems: 'center',
				justifyContent: side === 'left' ? 'flex-start' : 'flex-end',
				fontFamily: display,
				fontSize: Math.min(fontSize, 150),
				color: 'white',
				textShadow: '0 6px 30px rgba(0,0,0,0.9)',
				zIndex: 5,
			}}
		>
			{text.toUpperCase()}
		</div>
	);
};

export const Thumbnail: React.FC<ThumbnailProps> = ({left, right, main, secondary, background, accent}) => {
	const hasPeople = Boolean(main);
	// fitText measures with the real font, so wait until it is loaded
	const [handle] = useState(() => delayRender('fonts'));
	const [ready, setReady] = useState(false);
	useEffect(() => {
		fontsReady.then(() => {
			setReady(true);
			continueRender(handle);
		});
	}, [handle]);
	if (!ready) return null;
	return (
		<AbsoluteFill style={{background: `radial-gradient(circle at 50% 55%, ${accent} 0%, #3a0008 38%, #050505 75%)`}}>
			{background ? (
				<Img
					src={staticFile(background)}
					style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', opacity: hasPeople ? 0.25 : 0.7, filter: 'contrast(1.2) saturate(0.7)'}}
				/>
			) : null}
			{secondary ? (
				<Img
					src={staticFile(secondary)}
					style={{
						position: 'absolute',
						bottom: 0,
						left: 230,
						height: '92%',
						filter: 'grayscale(1) sepia(1) hue-rotate(-50deg) saturate(6) brightness(0.75) contrast(1.2)',
						zIndex: 2,
					}}
				/>
			) : null}
			{main ? (
				<Img
					src={staticFile(main)}
					style={{
						position: 'absolute',
						bottom: 0,
						left: '50%',
						transform: 'translateX(-46%)',
						height: '100%',
						filter: 'drop-shadow(0 0 18px rgba(255,255,255,0.35)) contrast(1.12) saturate(1.1)',
						zIndex: 3,
					}}
				/>
			) : null}
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.7) 100%)', zIndex: 4}} />
			{hasPeople ? (
				<>
					<SideWord text={left} side="left" />
					<SideWord text={right} side="right" />
				</>
			) : (
				<AbsoluteFill style={{justifyContent: 'center', padding: '0 60px', zIndex: 5}}>
					<div style={{fontFamily: display, fontSize: 150, lineHeight: 1, color: 'white', textShadow: '0 8px 40px #000'}}>
						{left.toUpperCase()} <span style={{color: '#ffd400'}}>{right.toUpperCase()}</span>
					</div>
				</AbsoluteFill>
			)}
		</AbsoluteFill>
	);
};
