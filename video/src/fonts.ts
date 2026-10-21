// Fonts are bundled from npm (@fontsource) so rendering never depends on the network.
// The latin subset covers Spanish accents (á é í ó ú ñ ¿ ¡).
import {loadFont} from '@remotion/fonts';
import anton from '@fontsource/anton/files/anton-latin-400-normal.woff2';
import m600 from '@fontsource/montserrat/files/montserrat-latin-600-normal.woff2';
import m800 from '@fontsource/montserrat/files/montserrat-latin-800-normal.woff2';
import m900 from '@fontsource/montserrat/files/montserrat-latin-900-normal.woff2';

export const display = 'Anton';
export const body = 'Montserrat';

export const fontsReady = Promise.all([
	loadFont({family: display, url: anton, weight: '400'}),
	loadFont({family: body, url: m600, weight: '600'}),
	loadFont({family: body, url: m800, weight: '800'}),
	loadFont({family: body, url: m900, weight: '900'}),
]);
