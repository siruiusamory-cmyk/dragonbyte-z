typedef unsigned int BFWord;
typedef int BFSigned;
typedef long long BFWide;

struct BFDamageInputs {
    BFWord kind, flags, strength, power, weight, scale, critical_bonus;
    BFWord physical_defense, energy_defense, physical_select, energy_select;
    BFWord critical_random, variance_random, attack_direction, defend_direction;
    BFWord counter_active, counter_scale, reflection_scale;
};

struct BFDamageResult { BFWord critical, product, damage, reflection; };

BFWord bf_random(BFWord *a,BFWord *b) {
    BFWord first=(*a+0x02cbbc71)^*b;
    BFWord second=(((*b<<3)|(*b>>29))+0x0632d80f)^first;
    *a=first;
    *b=second;
    return first-second;
}

BFWord bf_random_range(BFWord random,BFWord limit) {
    return ((random&65535)*limit)>>16;
}

BFWord bf_ki_cost(BFWord maximum,BFWord modifier) {
    BFWord cost=(BFWord)((BFSigned)(maximum*3277+65535)>>16);
    return (BFWord)((BFSigned)(cost*modifier)>>4);
}

void bf_damage_math(const struct BFDamageInputs *in,struct BFDamageResult *out) {
    BFWord attack=in->kind ? in->power : in->strength;
    BFWord weight=in->weight;
    BFWord critical=0;
    if (!in->kind) {
        if (in->flags!=3) critical=(in->critical_random&65535)<82*attack+in->critical_bonus;
        if (critical) weight+=(BFWord)((BFSigned)weight>>1);
        weight=(BFWord)((BFSigned)(attack*weight*3277)>>16);
    }
    BFWord defense=in->kind ? in->energy_defense : in->physical_defense;
    if (defense>=200) {
        defense=150+(defense>>2);
        if (defense>220) defense=220;
    }
    BFWord curve=attack+(BFWord)((BFSigned)(attack*attack*(attack+100))>>13);
    BFWord amount=(BFWord)((BFSigned)((221-defense)*weight*297)>>16);
    amount=(BFWord)((BFSigned)(in->scale*amount+1023)>>10);
    amount=(amount*(256+bf_random_range(in->variance_random,26)))>>8;
    out->critical=critical;
    out->product=amount*curve;
    BFWord selector=in->kind ? in->energy_select : in->physical_select;
    BFWord damage=(BFWord)(((BFWide)(BFSigned)out->product*selector+127)>>7);
    if (in->counter_active && ((in->attack_direction^1)==in->defend_direction) && damage)
        damage=(BFWord)(((BFWide)(BFSigned)in->counter_scale*(BFSigned)damage)>>16);
    out->damage=damage;
    out->reflection=0;
    if (!in->kind && damage && in->reflection_scale)
        out->reflection=(BFWord)(((BFWide)(BFSigned)in->reflection_scale*(BFSigned)damage)>>8);
}
