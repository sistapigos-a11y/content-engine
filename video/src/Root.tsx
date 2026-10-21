import React from 'react';
import {Composition, Still} from 'remotion';
import {Thumbnail} from './Thumbnail';
import {ThumbnailProps, VideoProps} from './types';
import {Video} from './Video';

const sample: VideoProps = {
	width: 1080,
	height: 1920,
	fps: 30,
	durationInFrames: 150,
	voice: 'sample/voice.wav',
	music: null,
	musicVolume: 0.08,
	scenes: [{from: 0, durationInFrames: 150, type: 'text', shots: [], onscreen: 'Nobody believed him'}],
	words: [],
	captions: true,
	accent: '#e50914',
	chapterLabel: 'CHAPTER',
};

const sampleThumb: ThumbnailProps = {left: 'Nobody', right: 'Believed', main: null, secondary: null, background: null, accent: '#e50914'};

export const Root: React.FC = () => (
	<>
		<Composition
			id="Video"
			component={Video}
			defaultProps={sample}
			width={1080}
			height={1920}
			fps={30}
			durationInFrames={150}
			calculateMetadata={({props}) => ({
				durationInFrames: props.durationInFrames,
				width: props.width,
				height: props.height,
				fps: props.fps,
			})}
		/>
		<Still id="Thumbnail" component={Thumbnail} defaultProps={sampleThumb} width={1280} height={720} />
	</>
);
