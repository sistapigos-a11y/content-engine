// Props are written by the Python pipeline (engine/render.py). All paths are relative
// to the job folder, which is passed to Remotion as --public-dir.

export type Shot = {
	src: string;
	kind: 'video' | 'image';
	durationInFrames: number;
};

export type SceneType = 'broll' | 'photo' | 'text' | 'quote';

export type Scene = {
	from: number;
	durationInFrames: number;
	type: SceneType;
	shots: Shot[];
	onscreen?: string;
	person?: string;
	chapter?: {index: number; title: string};
};

export type Word = {text: string; startMs: number; endMs: number};

export type VideoProps = {
	width: number;
	height: number;
	fps: number;
	durationInFrames: number;
	voice: string;
	music: string | null;
	musicVolume: number;
	scenes: Scene[];
	words: Word[];
	captions: boolean;
	accent: string;
	chapterLabel: string;
};

export type ThumbnailProps = {
	left: string;
	right: string;
	main: string | null; // transparent PNG cut-out of the main person
	secondary: string | null; // second person, tinted in the accent colour
	background: string | null; // used when there is no person (e.g. mysteries)
	accent: string;
};
