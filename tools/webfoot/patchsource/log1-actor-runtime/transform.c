typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef void (*Method)(u8 *);
typedef void (*Draw)(u8 *,void *);
struct Frame { const u32 *primary,*follower; const u16 *palette,*follower_palette; };
extern const struct Frame frames[11];
extern const Draw bounded_draw;
#define WORD(p,o) (*(u32 *)((u8 *)(p)+(o)))
#define BYTE(p,o) (*((u8 *)(p)+(o)))
#define LIST ((volatile u32 *)0x03000610)
#define BANKS ((volatile u32 *)0x03000994)

static int owner_live(u8 *owner) {
    u32 address=(u32)owner;
    if (address<0x02003840 || address>=0x02005040 || (address&63)) return 0;
    unsigned slot=(address-0x02003840)>>6;
    if (!(((volatile u8 *)0x030007a0)[slot>>3]&(1u<<(slot&7)))) return 0;
    return WORD(owner,0x1c)==0x085c1884 && WORD(owner,0x34)==0x08542a54;
}

extern int generic_visible(u8 *);
extern void generic_draw(u8 *,void *);

int transform_visible(u8 *actor) { return generic_visible(actor); }
void transform_draw(u8 *actor,void *context) { generic_draw(actor,context); }

static int palette_after_release(u8 *actor,const u16 *palette) {
    unsigned released=BYTE(actor,0x0d)&15;
    if (((int (*)(u8 *))0x0800bea9)(actor)) released=BYTE(actor,0x0d)>>4;
    for (unsigned bank=0;bank<16;++bank) {
        unsigned refs=BANKS[bank*2];
        if (bank==released && refs) --refs;
        if (!refs) return 1;
        const u16 *source=(const u16 *)BANKS[bank*2+1];
        if (!source) continue;
        unsigned colour;
        for (colour=1;colour<16;++colour) if (source[colour]!=palette[colour]) break;
        if (colour==16) return 1;
    }
    return 0;
}

void transform_advance(u8 *actor) {
    if (!owner_live(actor)) { ((Method)0x0800c9e3)(actor); return; }
    unsigned tick=BYTE(actor,0x10);
    unsigned frame=(tick*37)>>8;
    BYTE(actor,0x10)=tick+1;
    BYTE(actor,0x12)=frame>10 ? 10 : frame;
    if (tick+1<80) return;
    const u32 *target=(const u32 *)0x085c1f64;
    u32 definition[11];
    const u32 *bound=target;
    if (!palette_after_release(actor,(const u16 *)target[9])) {
        for (unsigned i=0;i<11;++i) definition[i]=target[i];
        unsigned bank=BYTE(actor,0x0d)&15;
        if (((int (*)(u8 *))0x0800bea9)(actor)) bank=BYTE(actor,0x0d)>>4;
        definition[9]=BANKS[bank*2+1];
        bound=definition;
    }
    ((void (*)(u8 *,const u32 *,u32,u32))0x080024b9)(actor,bound,0,0);
    WORD(actor,0x1c)=(u32)target;
    ((Method)((u32 *)WORD(actor,0x34))[2])(actor);
    *(volatile u32 *)0x030007e0=72;
}
