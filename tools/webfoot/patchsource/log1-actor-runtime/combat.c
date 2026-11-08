extern const signed char projectile_boxes[4][4][4];
extern const short donor_player_bodies[2][4][4];

static int projectile_owned(u8 *actor) {
    u8 *owner=(u8 *)WORD(actor,0x3c);
    if ((u32)owner<0x02003840 || (u32)owner>=0x02005040 || ((u32)owner&63)) return 0;
    u32 art=WORD(owner,0x1c);
    return art==0x085c1884 || art==0x085c1f64;
}

static int imported_projectile(u8 *actor) {
    u32 row=WORD(actor,0x34);
    return (row==0x081c7b28 || row==0x081c7b3c) && projectile_owned(actor);
}

void projectile_charge_init(u8 *actor) {
    ((Method)0x0800b4ed)(actor);
    if (projectile_owned(actor)) WORD(actor,0x30)=0;
}

void projectile_charge_advance(u8 *actor) {
    if (projectile_owned(actor) && WORD(actor,0x30)<16) ++WORD(actor,0x30);
    ((Method)0x0800b4af)(actor);
}

void projectile_charge_update(u8 *actor) {
    if (projectile_owned(actor) && !(*(volatile u16 *)0x03003d12&2)) {
        ((void (*)(u8 *,u32))0x0800b437)(actor,0);
        if (WORD(actor,0x34)!=0x081c7b14 || WORD(actor,0x30)<16) return;
    }
    ((Method)0x0800b4fb)(actor);
}

void projectile_init(u8 *actor) {
    ((Method)0x0800b555)(actor);
    if (imported_projectile(actor)) {
        BYTE(actor,0x10)=0;
        u8 *owner=(u8 *)WORD(actor,0x3c);
        unsigned direction=BYTE(actor,0x13)&3;
        const short *body=donor_player_bodies[WORD(owner,0x1c)==0x085c1f64][direction];
        int x=(body[0]+body[2])>>1,y=(body[1]+body[3])>>1;
        if (direction==0) y=0;
        else if (direction==2) x=body[0];
        else if (direction==3) x=body[2];
        *(u16 *)(actor+0x20)=*(short *)(owner+0x20)+x;
        *(u16 *)(actor+0x22)=*(short *)(owner+0x22)+y;
    }
}

static void projectile_box(u8 *actor,short *rect) {
    unsigned frame=BYTE(actor,0x12);
    if (frame>3) frame=3;
    const signed char *box=projectile_boxes[BYTE(actor,0x13)&3][frame];
    rect[0]=*(short *)(actor+0x20)+box[0];
    rect[1]=*(short *)(actor+0x22)+box[1];
    rect[2]=rect[0]+box[2];
    rect[3]=rect[1]+box[3];
}

void projectile_update(u8 *actor) {
    if (!imported_projectile(actor)) { ((Method)0x0800b5a3)(actor); return; }
    *(u16 *)(actor+0x20)+=*(short *)(actor+0x28);
    *(u16 *)(actor+0x22)+=*(short *)(actor+0x2a);
    unsigned age=BYTE(actor,0x10)+1;
    if (age==32) age=16;
    BYTE(actor,0x10)=age;
    unsigned frame=age>>3;
    if (frame>3) frame=(frame&1)+2;
    BYTE(actor,0x12)=frame;
    struct { short rect[4]; u32 power,flag; u8 kind,padding[3]; u32 owner; } hit;
    projectile_box(actor,hit.rect);
    const short *camera=(const short *)0x03000608;
    unsigned direction=BYTE(actor,0x13)&3;
    int inside=direction==0 ? hit.rect[1]<camera[1]+160 :
        direction==1 ? hit.rect[3]>camera[1] :
        direction==2 ? hit.rect[2]>camera[0] : hit.rect[0]<camera[0]+240;
    if (!inside) { ((Method)0x080028c5)(actor); return; }
    hit.power=WORD(actor,0x2c);
    hit.flag=BYTE(actor,0x16)!=0;
    hit.kind=0;
    hit.padding[0]=hit.padding[1]=hit.padding[2]=0;
    hit.owner=WORD(WORD(actor,0x3c),0x3c);
    int clear=((int (*)(u32,void *,u32))0x08004ffb)(*(u32 *)0x03000600,&hit,2);
    int contact=clear && ((int (*)(u32,void *))0x0800283d)(1,&hit);
    if (!clear || contact) ((void (*)(u8 *,u32))0x08002467)(actor,2);
}

void projectile_advance(u8 *actor) {
    if (!imported_projectile(actor)) ((Method)0x0800aefb)(actor);
}

void projectile_impact(u8 *actor) {
    if (!imported_projectile(actor)) { ((Method)0x0800b4cb)(actor); return; }
    if (BYTE(actor,0x10)++>=16) ((Method)0x080028c5)(actor);
}

int projectile_visible(u8 *actor) {
    if (!imported_projectile(actor)) return ((int (*)(u8 *))0x0800af81)(actor);
    unsigned index=WORD(actor,0x34)==0x081c7b3c ? 4 : BYTE(actor,0x12);
    if (index>4) index=3;
    const struct RenderFrame *frame=&projectile_frames[BYTE(actor,0x13)&3][index];
    u32 copy[16];
    for (unsigned i=0;i<16;++i) copy[i]=((u32 *)actor)[i];
    WORD(copy,8)=(u32)frame->pieces[0].table;
    int visible=((int (*)(u8 *))0x0800af81)((u8 *)copy);
    ((u32 *)actor)[0]=copy[0];
    ((u32 *)actor)[1]=copy[1];
    return visible;
}

extern const short donor_melee_rects[4][4];

int melee_contact(u8 *defender,const short *target) {
    (void)defender;
    u8 *player=*(u8 **)0x030007b8;
    u32 art=WORD(player,0x1c);
    if (art!=0x085c1884 && art!=0x085c1f64) {
        u32 point=((u32 (*)(void))0x08003447)();
        int x=(short)point,y=(short)(point>>16);
        return x>=target[0] && x<target[2] && y>=target[1] && y<target[3];
    }
    const short *rect=donor_melee_rects[BYTE(player,0x13)&3];
    int x=*(short *)(player+0x20),y=*(short *)(player+0x22);
    return x+rect[0]<target[2] && target[0]<x+rect[2] &&
        y+rect[1]<target[3] && target[1]<y+rect[3];
}
