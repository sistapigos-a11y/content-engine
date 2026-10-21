import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {Captions} from './components/Captions';
import {SceneView} from './components/SceneView';
import {VideoProps} from './types';

export const Video: React.FC<VideoProps> = ({scenes, voice, music, musicVolume, words, captions, accent, chapterLabel}) => {
	return (
		<AbsoluteFill style={{backgroundColor: '#050505'}}>
			{scenes.map((s, i) => (
				<Sequence key={i} from={s.from} durationInFrames={s.durationInFrames}>
					<SceneView scene={s} accent={accent} chapterLabel={chapterLabel} />
				</Sequence>
			))}
			{/* cinematic vignette */}
			<AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.65) 100%)'}} />
			{captions ? <Captions words={words} accent={accent} /> : null}
			<Audio src={staticFile(voice)} />
			{music ? <Audio src={staticFile(music)} volume={musicVolume} loop /> : null}
		</AbsoluteFill>
	);
};
