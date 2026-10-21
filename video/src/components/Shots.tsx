import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Shot} from '../types';

const ImageShot: React.FC<{src: string; duration: number; index: number}> = ({src, duration, index}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const t = frame / Math.max(1, duration);
	// alternate push-in / pull-out and drift direction so consecutive photos feel different
	const zoomIn = index % 2 === 0;
	const scale = zoomIn ? 1.04 + 0.12 * t : 1.16 - 0.12 * t;
	const drift = (index % 3 === 0 ? -1 : 1) * 30 * t;
	const portraitCanvas = height > width;
	return (
		<AbsoluteFill>
			{/* blurred fill so any photo ratio fits the canvas */}
			<Img
				src={staticFile(src)}
				style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(40px) brightness(0.45)', transform: 'scale(1.2)'}}
			/>
			<AbsoluteFill style={{transform: `scale(${scale}) translateX(${drift}px)`}}>
				<Img
					src={staticFile(src)}
					style={{width: '100%', height: '100%', objectFit: portraitCanvas ? 'cover' : 'contain'}}
				/>
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

const VideoShot: React.FC<{src: string; duration: number}> = ({src, duration}) => {
	const frame = useCurrentFrame();
	const scale = interpolate(frame, [0, duration], [1.0, 1.08]);
	return (
		<AbsoluteFill style={{transform: `scale(${scale})`}}>
			<OffthreadVideo
				src={staticFile(src)}
				muted
				style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'saturate(0.85) contrast(1.08)'}}
			/>
		</AbsoluteFill>
	);
};

const Fade: React.FC<{children: React.ReactNode}> = ({children}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
	return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

export const Shots: React.FC<{shots: Shot[]; dim?: number}> = ({shots, dim = 0}) => {
	let from = 0;
	return (
		<AbsoluteFill style={{background: 'radial-gradient(circle at 50% 40%, #2a0a0e 0%, #050505 75%)'}}>
			{shots.map((s, i) => {
				const seq = (
					<Sequence key={i} from={from} durationInFrames={s.durationInFrames} layout="none">
						<Fade>
							{s.kind === 'video' ? (
								<VideoShot src={s.src} duration={s.durationInFrames} />
							) : (
								<ImageShot src={s.src} duration={s.durationInFrames} index={i} />
							)}
						</Fade>
					</Sequence>
				);
				from += s.durationInFrames;
				return seq;
			})}
			{dim > 0 ? <AbsoluteFill style={{backgroundColor: `rgba(0,0,0,${dim})`}} /> : null}
		</AbsoluteFill>
	);
};
