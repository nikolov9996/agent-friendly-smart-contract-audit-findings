---
id: 25656
severity: "Medium"
---

# BlsBn254 is not available in certain chains due to hardcoded gas limit

## Description



## Proof of Concept

The [ZIP-11. V28 Precompile Upgrade](<https://www.tally.xyz/gov/zksync/proposal/54063168049426383294336598998322383147338444177076559098597792110160570100155?govId=eip155:324:0x76705327e682F2d96943280D99464Ab61219e34f>) is only available on the ZKSync mainnet (I don't think it's applied to the testnet), and it is not reproducible with the foundry fork test, so you need to test it directly on the mainnet.

Deploy the following code to the ZKSync Era mainnet and run it to see the gas cost. If you put the correct `input` in the `verify` function and experiment with incrementing `pairingGas` from 120_000, you will see that at around 161_000, the signature verification succeeds with `success` and `out[0]` set to 1. This is consistent with ZKSync's `80000 * k (k = 2)`.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Test {

    event Cost(uint256);
    event Out(bool, uint256);

    function test (uint256[12] memory input, uint256 pairingGas) public {
        (uint256 gasBefore, uint256 gasAfter, bool success, uint256 out) = verify(input, pairingGas);
        emit Cost(gasBefore - gasAfter);
        emit Out(success, out);
    }

    function verify (uint256[12] memory input, uint256 pairingGas) public view returns (uint256, uint256, bool, uint256) {
        uint256[1] memory out;
        bool success;

        uint256 gasBefore = gasleft();
        // solium-disable-next-line security/no-inline-assembly
        assembly {
            success := staticcall(pairingGas, 8, input, mul(12, 0x20), out, 0x20)
        }
        uint256 gasAfter = gasleft();
        return (gasBefore, gasAfter, success, out[0]);
    }
}
```

Use the following as the `input` parameter, created with the correct signature and key value. This is the value from the test code.

```json
[
17542794946843030738197687269502130768488764040084025709702018229683082027107, 21243454333462907454433938848788936660904069824545612138480299027504168819393, 11559732032986387107991004021392285783925812861821192530917403151452391805634, 10857046999023057135944570762232829481370756359578518086990519993285655852781, 17805874995975841540914202342111839520379459829704422454583296818431106115052, 13392588948715843804641432497768002650278120570034223513918757245338268106653, 6152845192698230377440204073057238033424791113774748884801148069022325658846, 13760496706863554449593094343798996929546352261485265365831743695186162488392, 10168917783125035928329339378130255896597415372015030444874307897081997728948, 15338339620195733484325031668011173090672215643291231872576243132177438055881, 10104509023153927337647655231628382133731833653099790728025758502925918550767, 13448048280709447326318302930315758447948705837394892676501482696723894570897
]
```

## Recommendation

The gas cost required to call Precompile may be changed in the future and can differ between chains. Therefore, instead of using `PAIRING_CHECK_GAS_LIMIT`, you should use a variable that can be set by an administrator.
