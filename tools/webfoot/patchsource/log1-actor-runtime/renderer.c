struct Piece { const u32 *table; const u16 *palette; };
struct RenderFrame { u32 count; const struct Piece *pieces; };
struct NativeFrame { u32 cell[4],table[4]; struct Piece pieces[2]; struct RenderFrame frame; };
struct Binding { u32 art, row, kind, count; const struct RenderFrame *directions[4]; };
extern const struct Binding bindings[];
extern const u32 binding_count;
extern const struct RenderFrame projectile_frames[4][5];
static int imported_projectile(u8 *actor);
static int hidden_projectile(u8 *actor);
int generic_visible(u8 *actor);
extern void original_render(unsigned, unsigned);
struct FrameBanks { u32 magic, native_mask; u16 palettes[16][16],used[16]; u32 refusals; const u16 *planned[16]; };

static int imported_character(u8 *actor) {
    u32 art=WORD(actor,0x1c);
    return art==0x085c1884 || art==0x085c1f64 || art==0x085c1eb4 || art==0x085c1aec || art==0x085c1b18;
}

static const struct Binding *binding_for(u8 *actor) {
    if (!imported_character(actor)) return (void *)0;
    for (unsigned i=0;i<binding_count;++i)
        if (bindings[i].art==WORD(actor,0x1c) && bindings[i].row==WORD(actor,8)) return &bindings[i];
    return (void *)0;
}

static const struct RenderFrame *render_frame_for(u8 *actor,struct NativeFrame *native) {
    if (hidden_projectile(actor)) return (void *)0;
    if (owner_live(actor)) {
        unsigned index=BYTE(actor,0x12);
        if (index>10) index=10;
        const struct Frame *source=&frames[index];
        native->pieces[0]=(struct Piece){source->primary,source->palette};
        native->pieces[1]=(struct Piece){source->follower,source->follower_palette};
        native->frame=(struct RenderFrame){source->follower ? 2 : 1,native->pieces};
        return &native->frame;
    }
    const struct Binding *binding=binding_for(actor);
    unsigned index=BYTE(actor,0x12);
    if (!binding) {
        if (imported_projectile(actor))
            return &projectile_frames[BYTE(actor,0x13)&3][WORD(actor,0x34)==0x081c7b3c ? 4 : (index>3 ? 3 : index)];
        u32 art=WORD(actor,0x1c);
        if (!imported_character(actor)) return (void *)0;
        const u32 *cell=(const u32 *)((u32 *)WORD(actor,8))[BYTE(actor,0x13)&3];
        for (unsigned i=0;i<4;++i) { native->cell[i]=cell[i];native->table[i]=(u32)native->cell; }
        native->cell[3]+=index*BYTE(cell,8)*32;
        native->pieces[0]=(struct Piece){native->table,(const u16 *)WORD(art,0x24)};
        native->frame=(struct RenderFrame){1,native->pieces};
        return &native->frame;
    }
    if (binding->kind==0) index=BYTE(actor,0x10)>240;
    else if (binding->kind==1) index=(BYTE(actor,0x10)>>3)&3;
    else if (binding->kind==3) index=(BYTE(actor,0x10)>>3)&1;
    if (index>=binding->count) index=binding->count-1;
    return &binding->directions[BYTE(actor,0x13)&3][index];
}

static const u16 *render_palette(u8 *actor,const struct Piece *piece) {
    if (WORD(actor,0x18)==0x08011f18)
        return (const u16 *)BANKS[(BYTE(actor,0x0d)&15)*2+1];
    return piece->palette;
}

struct Pending { u32 magic,mask; u16 imported,shown,depth,claim; u16 colours[16][15]; u16 touched,scratch_from,scratch_to; };

static struct Pending *queue(void) {
    struct Pending *pending=(struct Pending *)0x02013024;
    if (pending->magic!=0x504e4444) {
        pending->magic=0x504e4444;
        pending->mask=0;
        pending->imported=pending->shown=pending->depth=pending->claim=0;
        pending->touched=pending->scratch_from=pending->scratch_to=0;
    }
    return pending;
}

static void upload(unsigned bank,const u16 *palette) {
    struct Pending *pending=queue();
    for (unsigned i=1;i<16;++i) pending->colours[bank][i-1]=palette[i];
    pending->mask|=1u<<bank;
}

void oam_commit(void) {
    struct Pending *pending=queue();
    for (unsigned bank=0;bank<16;++bank) {
        if (!(pending->mask&(1u<<bank))) continue;
        volatile u16 *target=(volatile u16 *)(0x05000200+bank*32);
        for (unsigned i=1;i<16;++i) target[i]=pending->colours[bank][i-1];
    }
    for (unsigned bank=0;bank<16;++bank) {
        if (!(pending->touched&(1u<<bank)) || (pending->mask&(1u<<bank)) || !BANKS[bank*2+1]) continue;
        volatile u16 *target=(volatile u16 *)(0x05000200+bank*32);
        for (unsigned i=1;i<16;++i) target[i]=((const u16 *)BANKS[bank*2+1])[i];
    }
    for (unsigned i=pending->scratch_from*8;i<pending->scratch_to*8;++i) ((volatile u32 *)0x06010000)[i]=0;
    pending->touched=pending->scratch_from=pending->scratch_to=0;
    pending->mask=0;
    pending->shown=pending->imported;
    volatile u32 *dma=(volatile u32 *)0x040000d4;
    dma[0]=0x0202be24;
    dma[1]=0x07000000;
    ((volatile u16 *)dma)[4]=0x100;
    ((volatile u16 *)dma)[5]=0x8400;
}

static unsigned entry_tiles(volatile u16 *entry) {
    static const u8 tiles[3][4]={{1,4,16,64},{2,4,8,32},{2,4,8,32}};
    unsigned shape=entry[0]>>14;
    return shape<3 ? tiles[shape][entry[1]>>14]<<(entry[0]>>13&1) : 0;
}

#define PAIR(i) (u16)(1u<<((i)&15)|1u<<((i)>>4))
#define PAIR4(i) PAIR(i),PAIR(i+1),PAIR(i+2),PAIR(i+3)
#define PAIR16(i) PAIR4(i),PAIR4(i+4),PAIR4(i+8),PAIR4(i+12)
#define PAIR64(i) PAIR16(i),PAIR16(i+16),PAIR16(i+32),PAIR16(i+48)
static const u16 pixel_pairs[256]={PAIR64(0),PAIR64(64),PAIR64(128),PAIR64(192)};

static __attribute__((noinline)) unsigned tile_colours(unsigned tile,unsigned count) {
    const volatile u32 *words=(const volatile u32 *)(0x06010000+tile*32);
    unsigned n=count*8,mask=0;
    if (tile*8+n>0x2000) n=0x2000-tile*8;
    for (unsigned i=0;i<n;++i) {
        unsigned word=words[i];
        if (word) mask|=pixel_pairs[word&255]|pixel_pairs[word>>8&255]|pixel_pairs[word>>16&255]|pixel_pairs[word>>24];
    }
    return mask&~1u;
}

static __attribute__((noinline)) void recolour(volatile u16 *copy,const volatile u16 *source,unsigned count,const u8 *lookup) {
    for (unsigned k=0;k<count;++k) {
        unsigned word=source[k];
        copy[k]=lookup[word&15]|lookup[word>>4&15]<<4|lookup[word>>8&15]<<8|lookup[word>>12]<<12;
    }
}

static unsigned colour_hash(unsigned value) {
    return (value^value>>5^value>>10)&31;
}

static int blank(volatile u16 *entry) {
    if ((entry[0]&0x300)==0x200) return 1;
    if (entry[0]&0x2000) return 0;
    unsigned tile=entry[2]&0x3ff,n=entry_tiles(entry)*8;
    volatile u32 *words=(volatile u32 *)(0x06010000+tile*32);
    for (unsigned i=0;i<n && tile*8+i<0x2000;++i) if (words[i]) return 0;
    return 1;
}

static unsigned bank_used(const u8 *chain,unsigned link) {
    unsigned mask=1;
    for (;link;link=chain[link-1]) {
        volatile u16 *entry=(volatile u16 *)(0x07000000+(link-1)*8);
        mask|=tile_colours(entry[2]&0x3ff,entry_tiles(entry));
    }
    return mask;
}

static unsigned find_colour(const u8 *table,const u16 *value,unsigned colour) {
    unsigned h=colour_hash(colour);
    while (table[h]) {
        if (value[table[h]]==colour) return table[h];
        h=(h+1)&31;
    }
    return 0;
}

static unsigned find_free(u16 *used,const u16 *taken,const u8 *chain,const u8 *head,unsigned banks,unsigned *found) {
    for (unsigned t=0;t<16;++t) {
        if (!(banks&(1u<<t))) continue;
        if (!used[t]) used[t]=bank_used(chain,head[t]);
        unsigned s=1;
        while (s<16 && ((used[t]|taken[t])>>s&1)) ++s;
        if (s<16) { *found=t; return s; }
    }
    return 0;
}

static unsigned insert(unsigned at,unsigned *orig,u8 *blanks,u16 attr0,u16 attr1,u16 attr2) {
    volatile u16 *oam=(volatile u16 *)0x07000000;
    unsigned h=at+1;
    while (h<128 && !blanks[h]) ++h;
    if (h<128) {
        for (;h>at+1;--h) {
            for (unsigned k=0;k<3;++k) oam[h*4+k]=oam[h*4-4+k];
            blanks[h]=blanks[h-1];
        }
        ++at;
    } else {
        h=at;
        while (!blanks[h]) --h;
        if (h<*orig) --*orig;
        for (;h<at;++h) {
            for (unsigned k=0;k<3;++k) oam[h*4+k]=oam[h*4+4+k];
            blanks[h]=blanks[h+1];
        }
    }
    oam[at*4+1]=attr1;
    oam[at*4+2]=attr2;
    oam[at*4]=attr0;
    blanks[at]=0;
    return at;
}

static int tile_empty(unsigned tile) {
    volatile u32 *words=(volatile u32 *)(0x06010000+tile*32);
    for (unsigned i=0;i<8;++i) if (words[i]) return 0;
    return 1;
}

static int split_bank(unsigned bank,unsigned allowed,u16 *used,u16 *taken,struct Pending *pending) {
    volatile u16 *palette=(volatile u16 *)0x05000200;
    unsigned dispcnt=*(volatile u16 *)0x04000000;
    if (!(dispcnt&0x40) || (dispcnt&7)>2) return 0;
    unsigned colours=0,entries=0,tiles=0,spare=0,floor=0,l0=~0u,l1=0,l2=0;
    unsigned scratch_from=pending->scratch_from,scratch_to=pending->scratch_to;
    u8 blanks[128],chain[128],head[16];
    for (unsigned t=0;t<16;++t) head[t]=0;
    for (unsigned e=0;e<128;++e) {
        volatile u16 *entry=(volatile u16 *)(0x07000000+e*8);
        unsigned a0=entry[0],a1=entry[1],a2=entry[2];
        if (a0==l0 && a1==l1 && a2==l2 && blanks[e-1]) { blanks[e]=1; ++spare; continue; }
        l0=a0;
        l1=a1;
        l2=a2;
        unsigned tile=a2&0x3ff,n=entry_tiles(entry);
        if ((a0&0x300)!=0x200 && tile+n>floor && (!scratch_to || tile<scratch_from || tile>=scratch_to)) floor=tile+n;
        blanks[e]=blank(entry);
        if (blanks[e]) { ++spare; continue; }
        if (a0&0x2000) return 0;
        chain[e]=head[a2>>12];
        head[a2>>12]=e+1;
        if (a2>>12!=bank) continue;
        colours|=tile_colours(tile,n);
        ++entries;
        tiles+=n;
    }
    if (!entries) return 1;
    u8 home[16],slot[16],alias[16],table[32];
    u16 match[16],value[16];
    unsigned groups=0,count=0,fresh=0,remaining=0;
    for (unsigned k=0;k<32;++k) table[k]=0;
    for (unsigned i=1;i<16;++i) {
        if (!(colours&(1u<<i))) continue;
        value[i]=palette[bank*16+i]&0x7fff;
        unsigned h=colour_hash(value[i]);
        while (table[h] && value[table[h]]!=value[i]) h=(h+1)&31;
        alias[i]=table[h] ? table[h] : i;
        if (!table[h]) { table[h]=i; remaining|=1u<<i; }
    }
    for (unsigned t=0;t<16;++t) {
        match[t]=0;
        if (!(allowed&(1u<<t))) continue;
        for (unsigned s=1;s<16;++s) match[t]|=1u<<find_colour(table,value,palette[t*16+s]&0x7fff);
        match[t]&=~1u;
    }
    for (;;) {
        unsigned best=16,score=1;
        for (unsigned t=0;t<16;++t) {
            unsigned n=0;
            for (unsigned m=match[t]&remaining;m;m&=m-1) ++n;
            if (n>score) { score=n; best=t; }
        }
        if (best==16) break;
        for (unsigned s=1;s<16;++s) {
            unsigned i=find_colour(table,value,palette[best*16+s]&0x7fff);
            if (!i || !(remaining&(1u<<i))) continue;
            home[i]=best;
            slot[i]=s;
            taken[best]|=1u<<s;
            remaining&=~(1u<<i);
        }
        groups|=1u<<best;
        ++count;
    }
    for (unsigned i=1;i<16;++i) {
        if (!(remaining&(1u<<i))) continue;
        unsigned t=16,s=find_free(used,taken,chain,head,groups,&t);
        if (s) fresh|=1u<<i;
        for (unsigned b=0;!s && b<16;++b) {
            if (!(match[b]&(1u<<i))) continue;
            for (s=1;(palette[b*16+s]&0x7fff)!=value[i];++s) {}
            t=b;
        }
        if (!s) { s=find_free(used,taken,chain,head,allowed&~groups,&t); fresh|=1u<<i; }
        if (!s) return 0;
        home[i]=t;
        slot[i]=s;
        taken[t]|=1u<<s;
        if (!(groups&(1u<<t))) { groups|=1u<<t; ++count; }
    }
    for (unsigned i=1;i<16;++i) {
        if (!(colours&(1u<<i)) || alias[i]==i) continue;
        home[i]=home[alias[i]];
        slot[i]=slot[alias[i]];
    }
    unsigned need=tiles*count,top=pending->scratch_to ? pending->scratch_from : 1024;
    if (!count || spare<entries*(count-1)) return 0;
    for (;;) {
        if (top<floor+need) return 0;
        unsigned k=top;
        while (k>top-need && tile_empty(k-1)) --k;
        if (k==top-need) break;
        if (pending->scratch_to) return 0;
        top=k-1;
    }
    unsigned cursor=top-need;
    for (unsigned i=1;i<16;++i) {
        if (!(fresh&(1u<<i))) continue;
        palette[home[i]*16+slot[i]]=value[i];
        pending->touched|=1u<<home[i];
    }
    if (!pending->scratch_to) pending->scratch_to=top;
    pending->scratch_from=cursor;
    for (unsigned e=0;e<128;++e) {
        volatile u16 *entry=(volatile u16 *)(0x07000000+e*8);
        if (blanks[e] || entry[2]>>12!=bank) continue;
        unsigned n=entry_tiles(entry),mine=tile_colours(entry[2]&0x3ff,n);
        volatile u16 *source=(volatile u16 *)(0x06010000+(entry[2]&0x3ff)*32);
        u16 attr0=entry[0],attr1=entry[1],attr2=entry[2],parts[16];
        unsigned pieces=0;
        for (unsigned t=0;t<16;++t) {
            if (!(groups&(1u<<t))) continue;
            u8 lookup[16];
            unsigned part=0;
            for (unsigned j=0;j<16;++j) {
                lookup[j]=j && (colours&(1u<<j)) && home[j]==t ? slot[j] : 0;
                if (lookup[j] && (mine&(1u<<j))) part=1;
            }
            if (!part) continue;
            recolour((volatile u16 *)(0x06010000+cursor*32),source,n*16,lookup);
            parts[pieces++]=(attr2&0x0c00)|(t<<12)|cursor;
            cursor+=n;
        }
        unsigned orig=e,at=e;
        for (unsigned p=1;p<pieces;++p) at=insert(at,&orig,blanks,attr0,attr1,parts[p]);
        if (pieces) ((volatile u16 *)(0x07000000+orig*8))[2]=parts[0];
        e=at;
    }
    return 1;
}

void dialogue_yield(void) {
    struct Pending *pending=queue();
    if (!pending->depth++) pending->claim=31;
    unsigned free_bank=0;
    for (unsigned bank=0;bank<16;++bank) if (!BANKS[bank*2]) free_bank=bank;
    pending->claim|=1u<<free_bank;
    unsigned busy=pending->claim|pending->mask;
    for (unsigned i=0;i<256;++i) {
        volatile u16 *entry=(volatile u16 *)(i<128 ? 0x07000000+i*8 : 0x0202be24+(i-128)*8);
        if ((entry[0]&0x300)!=0x200) busy|=entry[0]&0x2000 ? 65535 : 1u<<(entry[2]>>12);
    }
    unsigned moving=pending->shown&pending->claim,moved=0,stuck=0;
    u8 target[16];
    for (unsigned bank=0;bank<16;++bank) {
        target[bank]=bank;
        if (!(moving&(1u<<bank))) continue;
        unsigned t=0;
        while (t<16 && (busy&(1u<<t))) ++t;
        target[bank]=t;
        if (t==16) { stuck=1; continue; }
        busy|=1u<<t;
        moved|=1u<<t;
        for (unsigned i=1;i<16;++i)
            ((volatile u16 *)(0x05000200+t*32))[i]=((volatile u16 *)(0x05000200+bank*32))[i];
    }
    for (unsigned i=0;i<256;++i) {
        volatile u16 *entry=(volatile u16 *)(i<128 ? 0x07000000+i*8 : 0x0202be24+(i-128)*8);
        if ((entry[0]&0x300)==0x200 || (entry[0]&0x2000)) continue;
        unsigned bank=entry[2]>>12;
        if (target[bank]!=bank && target[bank]!=16) entry[2]=(entry[2]&0x0fff)|(target[bank]<<12);
    }
    pending->shown=(pending->shown&~moving)|moved;
    if (!stuck) return;
    u16 used[16],taken[16];
    unsigned allowed=0;
    for (unsigned bank=0;bank<16;++bank) {
        used[bank]=taken[bank]=0;
        if (BANKS[bank*2] && BANKS[bank*2+1] && !((pending->claim|moved)&(1u<<bank))) allowed|=1u<<bank;
    }
    for (unsigned bank=0;bank<16;++bank) {
        if (target[bank]!=16 || split_bank(bank,allowed,used,taken,pending)) continue;
        for (unsigned i=0;i<256;++i) {
            volatile u16 *entry=(volatile u16 *)(i<128 ? 0x07000000+i*8 : 0x0202be24+(i-128)*8);
            if ((entry[0]&0x300)!=0x200 && !(entry[0]&0x2000) && entry[2]>>12==bank)
                entry[0]=(entry[0]&~0x300)|0x200;
        }
    }
}

void dialogue_close(void) {
    struct Pending *pending=queue();
    if (pending->depth) --pending->depth;
}

static int frame_bank(struct FrameBanks *state,const u16 *palette,unsigned mask,u8 *remap) {
    for (unsigned bank=0;bank<16;++bank) {
        unsigned used=state->used[bank];
        if (used==254) continue;
        unsigned limit=used==255 ? 15 : used;
        u16 candidate[16];
        for (unsigned i=1;i<=limit;++i) candidate[i]=state->palettes[bank][i];
        remap[0]=0;
        unsigned source;
        for (source=1;source<16;++source) {
            if (!(mask&(1u<<source))) continue;
            unsigned slot;
            u16 colour=palette[source]&0x7fff;
            for (slot=1;slot<=limit;++slot) if (candidate[slot]==colour) break;
            if (slot>limit) {
                if (used==255 || limit==15) break;
                candidate[++limit]=colour;
            }
            remap[source]=slot;
        }
        if (source<16) continue;
        if (used!=255) {
            for (unsigned i=1;i<=limit;++i) state->palettes[bank][i]=candidate[i];
            state->used[bank]=limit;
            upload(bank,state->palettes[bank]);
            queue()->imported|=1u<<bank;
        }
        return bank;
    }
    return -1;
}

static void draw_remapped(u8 *actor,void *context,const u32 *source_cell,
                          const u8 *source_tiles,unsigned bytes,int bank,const u8 *remap) {
    u32 copy[16],cell[4],table[4],tile_words[128];
    u8 *tiles=(u8 *)tile_words;
    unsigned identity=1;
    for (unsigned j=0;j<16;++j) if (remap[j]!=j) { identity=0; break; }
    if (!identity) {
        u8 lookup[256];
        for (unsigned j=0;j<256;++j) lookup[j]=remap[j&15]|(remap[j>>4]<<4);
        for (unsigned j=0;j<bytes;++j) tiles[j]=lookup[source_tiles[j]];
    }
    for (unsigned j=0;j<4;++j) { cell[j]=source_cell[j];table[j]=(u32)cell; }
    cell[3]=(u32)(identity ? source_tiles : tiles);
    for (unsigned j=0;j<16;++j) copy[j]=((u32 *)actor)[j];
    WORD(copy,8)=(u32)table;
    BYTE(copy,0x0d)=bank;
    BYTE(copy,0x12)=0;
    if (((int (*)(u8 *))0x0800af81)((u8 *)copy)) bounded_draw((u8 *)copy,context);
}

static void prepare_mask(struct FrameBanks *state,void *context) {
    state->native_mask=0;
    struct Pending *pending=queue();
    unsigned external_mask=pending->depth ? pending->claim : 0;
    for (unsigned i=0;i<LIST[0] && i<96;++i)
        if (WORD(LIST[i+1],0x34)==0x08011480) external_mask|=31;
    unsigned entries=*(u16 *)context;
    if (entries>128) entries=128;
    for (unsigned i=0;i<entries;++i) {
        unsigned attribute=*(u16 *)(0x0202be24+i*8+4);
        state->native_mask|=1u<<(attribute>>12);
        if (*(u16 *)(0x0202be24+i*8)&0x2000) external_mask|=external_mask ? 31 : 65535;
    }
    state->native_mask|=external_mask;
    unsigned count=LIST[0];
    if (count>96) count=96;
    for (unsigned i=0;i<count;++i) {
        u8 *actor=(u8 *)LIST[i+1];
        if (imported_character(actor) || imported_projectile(actor) || hidden_projectile(actor)) continue;
        if (WORD(WORD(actor,0x34),12)==0x0800af81 || WORD(WORD(actor,0x34),12)==((u32)generic_visible|1)) {
            const short *viewport=(const short *)0x08011e1c;
            int x=*(short *)actor,y=*(short *)(actor+2);
            unsigned w=*(u16 *)(actor+4),h=*(u16 *)(actor+6);
            if (x+(int)w<=viewport[0] || x>=viewport[2] ||
                y+(int)h<=viewport[1] || y>=viewport[3]) continue;
        }
        unsigned bank=BYTE(actor,0x0d);
        state->native_mask|=1u<<(bank&15);
        if (bank>15) state->native_mask|=1u<<(bank>>4);
    }
    for (unsigned bank=0;bank<16;++bank) {
        state->used[bank]=(external_mask&(1u<<bank)) ? 254 :
            (state->native_mask&(1u<<bank)) ? 255 : 0;
        for (unsigned i=1;i<16;++i)
            state->palettes[bank][i]=state->used[bank]==255
                ? ((pending->touched&(1u<<bank)) ? ((const u16 *)BANKS[bank*2+1])[i]
                    : *(volatile u16 *)(0x05000200+bank*32+i*2))&0x7fff : 0;
    }
    const u16 *needed[16];
    unsigned demand=0,available=0;
    for (unsigned bank=0;bank<16;++bank) {
        state->planned[bank]=(void *)0;
        if (!state->used[bank]) ++available;
    }
    for (unsigned i=0;i<count;++i) {
        u8 *actor=(u8 *)LIST[i+1];
        struct NativeFrame native;
        const struct RenderFrame *frame=render_frame_for(actor,&native);
        if (!frame) continue;
        int x=*(short *)actor,y=*(short *)(actor+2);
        if (x+(int)*(u16 *)(actor+4)<=0 || x>=240 || y+(int)*(u16 *)(actor+6)<=0 || y>=160) continue;
        for (unsigned piece=0;piece<frame->count;++piece) {
            const u16 *palette=render_palette(actor,&frame->pieces[piece]);
            unsigned n;
            for (n=0;n<demand;++n) if (needed[n]==palette) break;
            if (n<demand) continue;
            if (demand==available) return;
            needed[demand++]=palette;
        }
    }
    unsigned assigned=0;
    for (unsigned bank=0;bank<16 && assigned<demand;++bank) {
        if (state->used[bank]) continue;
        const u16 *palette=needed[assigned++];
        state->planned[bank]=palette;
        state->used[bank]=15;
        for (unsigned i=1;i<16;++i) state->palettes[bank][i]=palette[i];
        upload(bank,palette);
        pending->imported|=1u<<bank;
    }
}

void render_frame(unsigned oam_start,unsigned tile_start) {
    volatile struct FrameBanks state;
    state.magic=0x53505254;
    state.refusals=0;
    state.native_mask=0x10000;
    queue()->imported=0;
    for (unsigned i=0;i<16;++i)
        if (BANKS[i*2] && BANKS[i*2+1]) upload(i,(const u16 *)BANKS[i*2+1]);
    __asm__ volatile("mov r8,%0"::"r"(&state):"r8","memory");
    original_render(oam_start,tile_start);
}

void framed_draw(u8 *actor,void *context,u32 address) {
    if (hidden_projectile(actor)) return;
    if (address<0x03000000 || address>=0x03008000 || WORD(address,0)!=0x53505254) {
        bounded_draw(actor,context);
        return;
    }
    struct FrameBanks *state=(struct FrameBanks *)address;
    if (state->native_mask==0x10000) prepare_mask(state,context);
    struct NativeFrame native;
        const struct RenderFrame *frame=render_frame_for(actor,&native);
    if (!frame) { bounded_draw(actor,context); return; }
    for (unsigned i=0;i<frame->count;++i) {
        const struct Piece *piece=&frame->pieces[i];
        const u16 *palette=render_palette(actor,piece);
        const u32 *source_cell=(const u32 *)piece->table[BYTE(actor,0x13)&3];
        unsigned bytes=BYTE(source_cell,8)*32;
        if (bytes>512) { ++state->refusals; return; }
        const u8 *source_tiles=(const u8 *)source_cell[3];
        u8 remap[16];
        for (unsigned j=0;j<16;++j) remap[j]=j;
        int bank=-1;
        for (unsigned j=0;j<16;++j)
            if (state->planned[j]==palette) { bank=j; break; }
        if (bank>=0) {
            draw_remapped(actor,context,source_cell,source_tiles,bytes,bank,remap);
            continue;
        }
        unsigned mask=0;
        for (unsigned j=0;j<bytes;++j)
            mask|=(1u<<(source_tiles[j]&15))|(1u<<(source_tiles[j]>>4));
        bank=frame_bank(state,palette,mask,remap);
        if (bank>=0) {
            draw_remapped(actor,context,source_cell,source_tiles,bytes,bank,remap);
            continue;
        }
        int colour_banks[16];
        u8 colour_slots[16];
        for (unsigned colour=1;colour<16;++colour) {
            colour_banks[colour]=-1;
            if (!(mask&(1u<<colour))) continue;
            bank=frame_bank(state,palette,1u<<colour,remap);
            if (bank<0) { ++state->refusals; return; }
            colour_banks[colour]=bank;
            colour_slots[colour]=remap[colour];
        }
        for (bank=0;bank<16;++bank) {
            unsigned found=0;
            remap[0]=0;
            for (unsigned colour=1;colour<16;++colour) {
                remap[colour]=colour_banks[colour]==bank ? colour_slots[colour] : 0;
                if (remap[colour]) found=1;
            }
            if (found) draw_remapped(actor,context,source_cell,source_tiles,bytes,bank,remap);
        }
    }
}

int generic_visible(u8 *actor) {
    if (hidden_projectile(actor)) return 0;
    struct NativeFrame native;
        const struct RenderFrame *frame=render_frame_for(actor,&native);
    if (!frame) return ((int (*)(u8 *))0x0800af81)(actor);
    int left=32767,top=32767,right=-32768,bottom=-32768;
    for (unsigned i=0;i<frame->count;++i) {
        const short *cell=(const short *)frame->pieces[i].table[BYTE(actor,0x13)&3];
        int x=cell[0],y=cell[1],x1=x+(u16)cell[2],y1=y+(u16)cell[3];
        if (x<left) left=x;
        if (y<top) top=y;
        if (x1>right) right=x1;
        if (y1>bottom) bottom=y1;
    }
    u32 copy[16],cell[4],table[4];
    for (unsigned i=0;i<16;++i) copy[i]=((u32 *)actor)[i];
    cell[0]=(u16)left|((u32)(u16)top<<16);
    cell[1]=(u16)(right-left)|((u32)(u16)(bottom-top)<<16);
    for (unsigned i=0;i<4;++i) table[i]=(u32)cell;
    WORD(copy,8)=(u32)table;
    int visible=((int (*)(u8 *))0x0800af81)((u8 *)copy);
    ((u32 *)actor)[0]=copy[0];
    ((u32 *)actor)[1]=copy[1];
    return visible;
}
