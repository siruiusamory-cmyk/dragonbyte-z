struct Piece { const u32 *table; const u16 *palette; };
struct RenderFrame { u32 count; const struct Piece *pieces; };
struct NativeFrame { u32 cell[4],table[4]; struct Piece pieces[2]; struct RenderFrame frame; };
struct Binding { u32 art, row, kind, count; const struct RenderFrame *directions[4]; };
extern const struct Binding bindings[];
extern const u32 binding_count;
extern const struct RenderFrame projectile_frames[4][5];
static int imported_projectile(u8 *actor);
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

static void upload(unsigned bank,const u16 *palette) {
    volatile u16 *target=(volatile u16 *)(0x05000200+bank*32);
    for (unsigned i=1;i<16;++i) target[i]=palette[i];
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
    unsigned external_mask=0;
    for (unsigned i=0;i<LIST[0] && i<96;++i)
        if (WORD(LIST[i+1],0x34)==0x08011480) external_mask=31;
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
        if (imported_character(actor) || imported_projectile(actor)) continue;
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
                ? (*(volatile u16 *)(0x05000200+bank*32+i*2))&0x7fff : 0;
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
    }
}

void render_frame(unsigned oam_start,unsigned tile_start) {
    volatile struct FrameBanks state;
    state.magic=0x53505254;
    state.refusals=0;
    state.native_mask=0x10000;
    for (unsigned i=0;i<16;++i)
        if (BANKS[i*2] && BANKS[i*2+1]) upload(i,(const u16 *)BANKS[i*2+1]);
    __asm__ volatile("mov r8,%0"::"r"(&state):"r8","memory");
    original_render(oam_start,tile_start);
}

void generic_draw(u8 *actor,void *context) {
    u32 address;
    __asm__ volatile("mov %0,r8":"=r"(address));
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
