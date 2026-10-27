/** Species-labeled photographs. Each file's title or description names the grass. See /credits/. */

export interface Photo {
  id: string;
  alt: string;
  /** Path without the -800/-1200 suffix or extension, under public/. */
  base: string;
  width: number;
  height: number;
  photographer: string;
  sourceName: string;
  sourceUrl: string;
  license: string;
  licenseUrl: string;
  /** Anything a reader should know about the caption. */
  note?: string;
}

export const GRASS_PHOTOS: Record<string, Photo> = {
  'kentucky-bluegrass': {
    id: 'kentucky-bluegrass',
    alt: 'A mowed lawn of Kentucky bluegrass (Poa pratensis), with a few small broadleaf plants in the turf.',
    base: '/images/grass/kentucky-bluegrass',
    width: 1200, height: 795,
    photographer: 'Ethan2039',
    sourceName: 'Wikimedia Commons: Poa pratensis lawn.jpg',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Poa_pratensis_lawn.jpg',
    license: 'CC BY-SA 4.0',
    licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/',
  },
  'tall-fescue': {
    id: 'tall-fescue',
    alt: 'Tall fescue (Festuca arundinacea) in a nursery pot. The species name is printed on the label in the pot.',
    base: '/images/grass/tall-fescue',
    width: 1200, height: 900,
    photographer: 'Forest & Kim Starr',
    sourceName: 'Wikimedia Commons: Starr 030603-0006 Festuca arundinacea.jpg',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Starr_030603-0006_Festuca_arundinacea.jpg',
    license: 'CC BY 3.0',
    licenseUrl: 'https://creativecommons.org/licenses/by/3.0/',
    note: 'The photograph is a labeled nursery plant at Haleakalā National Park, Maui, not a mowed home lawn. The label in the frame reads Festuca arundinacea.',
  },
  bermudagrass: {
    id: 'bermudagrass',
    alt: 'A mowed lawn of bermudagrass (Cynodon dactylon), called couch grass in the photographer’s caption, in Stanley, Tasmania.',
    base: '/images/grass/bermudagrass',
    width: 1200, height: 675,
    photographer: 'John Tann',
    sourceName: 'Wikimedia Commons: A lawn of Couch Grass (6700345007).jpg',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:A_lawn_of_Couch_Grass_(6700345007).jpg',
    license: 'CC BY 2.0',
    licenseUrl: 'https://creativecommons.org/licenses/by/2.0/',
    note: 'The file description names the lawn as Cynodon dactylon. “Couch grass” in that caption is this species, not quackgrass.',
  },
  'st-augustinegrass': {
    id: 'st-augustinegrass',
    alt: 'St. Augustinegrass (Stenotaphrum secundatum) in a lawn, showing wide blades and creeping stolons.',
    base: '/images/grass/st-augustinegrass',
    width: 1200, height: 900,
    photographer: 'Forest and Kim Starr',
    sourceName: 'Wikimedia Commons file of Stenotaphrum secundatum in a lawn at Honoapiilani Beach Park, Maui',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Starr-170321-0608-Stenotaphrum_secundatum-in_lawn-Honoapiilani_Beach_Park_Kaanapali-Maui_(33296732993).jpg',
    license: 'CC BY 3.0 US',
    licenseUrl: 'https://creativecommons.org/licenses/by/3.0/us/',
    note: 'The scientific name on the file is Stenotaphrum secundatum. The photographer’s caption also says “centipede grass,” which is a different species (Eremochloa ophiuroides). This photo is used only for St. Augustinegrass.',
  },
  zoysiagrass: {
    id: 'zoysiagrass',
    alt: 'Zoysiagrass (Zoysia japonica) growing as a dense patch beside a border of brown, worn turf.',
    base: '/images/grass/zoysiagrass',
    width: 1200, height: 1357,
    photographer: 'Show_ryu',
    sourceName: 'Wikimedia Commons: Zoysia japonica 1.JPG',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Zoysia_japonica_1.JPG',
    license: 'CC BY-SA 3.0',
    licenseUrl: 'https://creativecommons.org/licenses/by-sa/3.0/',
  },
  centipedegrass: {
    id: 'centipedegrass',
    alt: 'A centipedegrass lawn, pale green, with scattered dry blades.',
    base: '/images/grass/centipedegrass',
    width: 1200, height: 802,
    photographer: 'Vengolis',
    sourceName: 'Wikimedia Commons: Centipedegrass 00722.JPG',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Centipedegrass_00722.JPG',
    license: 'CC BY-SA 4.0',
    licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/',
    note: 'The file title and description say “Centipedegrass.” The file is in the Wikimedia category for Eremochloa ophiuroides. The description does not repeat the scientific name.',
  },
};

export const SHARE_IMAGE = '/og/lawn-numbers.jpg';
