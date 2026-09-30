---
id: 22495
severity: "Medium"
---

# Position Manager providing the wrong strike

## Description

When users mint position using PositionManager, users can provide strike that they want to be used for the trade. However, if the provided strike data is not exactly the same with IG's current strike, the minted position will be permanently stuck inside the PositionManager's contract.

When mint is called inside PositionManager, it will calculate the premium, transfer the required base token, and eventually call dvp.mint, providing the user's provided information.

```solidity
function mint(
    IPositionManager.MintParams calldata params
) external override returns (uint256 tokenId, uint256 premium) {
    IDVP dvp = IDVP(params.dvpAddr);
    if (params.tokenId != 0) {
        tokenId = params.tokenId;
        ManagedPosition storage position = _positions[tokenId];
        if (ownerOf(tokenId) != msg.sender) {
            revert NotOwner();
        }
        // Check token compatibility:
        if (position.dvpAddr != params.dvpAddr || position.strike != params.strike) {
            revert InvalidTokenID();
        }
        Epoch memory epoch = dvp.getEpoch();
        if (position.expiry != epoch.current) {
            revert PositionExpired();
        }
    }
    if ((params.notionalUp > 0 && params.notionalDown > 0) && (params.notionalUp != params.notionalDown)) {
        // If amount is a smile, it must be balanced:
        revert AsymmetricAmount();
    }
    uint256 obtainedPremium;
    uint256 fee;
    (obtainedPremium, fee) = dvp.premium(params.strike, params.notionalUp, params.notionalDown);

    // Transfer premium:
    // the DVP
    IERC20 baseToken = IERC20(dvp.baseToken());
    baseToken.safeTransferFrom(msg.sender, address(this), obtainedPremium);
    // Premium already include fee
    baseToken.safeApprove(params.dvpAddr, obtainedPremium);

    premium = dvp.mint(
        address(this),
        params.strike,
        params.notionalUp,
        params.notionalDown,
        params.expectedPremium,
        params.maxSlippage,
        params.nftAccessTokenId
    );
}
```

Inside dvp.mint, in this case, IG contract's mint, will use financeParameters.currentStrike instead of the user's provided strike:

```solidity
/// @inheritdoc IDVP
function mint(
    address recipient,
    uint256 strike,
    uint256 amountUp,
    uint256 amountDown,
    uint256 expectedPremium,
    uint256 maxSlippage,
    uint256 nftAccessTokenId
) external override returns (uint256 premium_) {
    strike;
    _checkNFTAccess(nftAccessTokenId, recipient, amountUp + amountDown);
    Amount memory amount_ = Amount({up: amountUp, down: amountDown});
    premium_ = _mint(recipient, financeParameters.currentStrike, amount_, expectedPremium, maxSlippage);
}
```

But when storing the position's information inside PositionManager, it uses user's provided strike instead of IG's current strike:

```solidity
function mint(
    IPositionManager.MintParams calldata params
) external override returns (uint256 tokenId, uint256 premium) {
    if (obtainedPremium > premium) {
        baseToken.safeTransferFrom(address(this), msg.sender, obtainedPremium - premium);
    }
    if (params.tokenId == 0) {
        // Mint token:
        tokenId = _nextId++;
        _mint(params.recipient, tokenId);
        Epoch memory epoch = dvp.getEpoch();
        // Save position:
        _positions[tokenId] = ManagedPosition({
            dvpAddr: params.dvpAddr,
            strike: params.strike,
            expiry: epoch.current,
            premium: premium,
            leverage: (params.notionalUp + params.notionalDown) / premium,
            notionalUp: params.notionalUp,
            notionalDown: params.notionalDown,
            cumulatedPayoff: 0
        });
    } else {
        ManagedPosition storage position = _positions[tokenId];
        // Increase position:
        position.premium += premium;
        position.notionalUp += params.notionalUp;
        position.notionalDown += params.notionalDown;
        /*
        When, within the same epoch, a user wants to buy, sell partially and then buy again, the leverage computation can fail due to decreased notional; in order to avoid this issue, we have to also adjust (decrease) the premium in the burn flow.
        */
        position.leverage = (position.notionalUp + position.notionalDown) / position.premium;
    }
    emit BuyDVP(tokenId, _positions[tokenId].expiry, params.notionalUp + params.notionalDown);
    emit Buy(params.dvpAddr, _positions[tokenId].expiry, premium, params.recipient);
}
```

If the provided strike data does not match IG's current strike price, the user's minted position using PositionManager will be stuck and cannot be burned. This happens because when burn is called and position.strike is provided, it will revert as it cannot find the corresponding positions inside IG contract.

This issue directly risks user's funds. Consider a scenario where users mint a position near the end of the rolling epoch, providing the old epoch's current price. However, when the user's transaction is executed, the epoch is rolled and new epoch's current price is used, causing the mentioned issue to occur, and users' positions and funds will be stuck.

## Proof of Concept

Add the following test to PositionManagerTest contract:
```solidity
function testMintAndBurnFail() public {
    (uint256 tokenId, ) = initAndMint();
    bytes4 PositionNotFound = bytes4(keccak256("PositionNotFound()"));
    vm.prank(alice);
    vm.expectRevert(PositionNotFound);
    pm.sell(
        IPositionManager.SellParams({
            tokenId: tokenId,
            notionalUp: 10 ether,
            notionalDown: 0,
            expectedMarketValue: 0,
            maxSlippage: 0.1e18
        })
    );
}
```

Modify initAndMint function to the following:
```solidity
function initAndMint() private returns (uint256 tokenId, IG ig) {
    vm.startPrank(admin);
    ig = new IG(address(vault), address(ap));
    ig.grantRole(ig.ROLE_ADMIN(), admin);
    ig.grantRole(ig.ROLE_EPOCH_ROLLER(), admin);
    vault.grantRole(vault.ROLE_ADMIN(), admin);
    vault.setAllowedDVP(address(ig));
    MarketOracle mo = MarketOracle(ap.marketOracle());
    mo.setDelay(ig.baseToken(), ig.sideToken(), ig.getEpoch().frequency, 0, true);

    Utils.skipDay(true, vm);
    ig.rollEpoch();
    vm.stopPrank();

    uint256 strike = ig.currentStrike();
    (uint256 expectedMarketValue, ) = ig.premium(0, 10 ether, 0);
    TokenUtils.provideApprovedTokens(admin, baseToken, DEFAULT_SENDER, address(pm), expectedMarketValue, vm);

    vm.prank(DEFAULT_SENDER);
    (tokenId, ) = pm.mint(
        IPositionManager.MintParams({
            dvpAddr: address(ig),
            notionalUp: 10 ether,
            notionalDown: 0,
            strike: strike + 1,
            recipient: alice,
            tokenId: 0,
            expectedPremium: expectedMarketValue,
            maxSlippage: 0.1e18,
            nftAccessTokenId: 0
        })
    );
    assertGe(1, tokenId);
    assertGe(1, pm.totalSupply());
}
```

Run the test:
forge test --match-contract PositionManagerTest --match-test testMintAndBurnFail -vvv

## Recommendation

When storing user position data inside PositionManager, query IG's current price and use it instead.
```solidity
function mint(
    IPositionManager.MintParams calldata params
) external override returns (uint256 tokenId, uint256 premium) {
    if (params.tokenId == 0) {
        // Mint token:
        tokenId = _nextId++;
        _mint(params.recipient, tokenId);
        Epoch memory epoch = dvp.getEpoch();
        uint256 currentStrike = dvp.currentStrike();
        // Save position:
        _positions[tokenId] = ManagedPosition({
            dvpAddr: params.dvpAddr,
            strike: currentStrike,
            expiry: epoch.current,
            premium: premium,
            leverage: (params.notionalUp + params.notionalDown) / premium,
            notionalUp: params.notionalUp,
            notionalDown: params.notionalDown,
            cumulatedPayoff: 0
        });
    } else {
        ManagedPosition storage position = _positions[tokenId];
        // Increase position:
        position.premium += premium;
        position.notionalUp += params.notionalUp;
        position.notionalDown += params.notionalDown;
        /*
        When, within the same epoch, a user wants to buy, sell partially and then buy again, the leverage computation can fail due to decreased notional; in order to avoid this issue, we have to also adjust (decrease) the premium in the burn flow.
        */
        position.leverage = (position.notionalUp + position.notionalDown) / position.premium;
    }
    emit BuyDVP(tokenId, _positions[tokenId].expiry, params.notionalUp + params.notionalDown);
    emit Buy(params.dvpAddr, _positions[tokenId].expiry, premium, params.recipient);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a strike‑mismatch bug in the PositionManager contract that causes minted positions to become permanently non‑redeemable when the strike supplied by the user does not exactly match the current strike used by the underlying IG (Interest‑Generating) contract. The root cause is that PositionManager records the user‑provided strike value in its internal ManagedPosition struct, while the IG contract’s mint function internally substitutes the protocol’s currentStrike for the supplied strike. Consequently, the on‑chain record and the protocol’s internal accounting diverge. When a user later attempts to burn or sell the position, the burn logic reads the stored strike from PositionManager and passes it to the IG contract, which expects the current strike. Because the two values differ, the IG contract cannot locate the position and reverts (e.g., with PositionNotFound), leaving the NFT and the associated premium locked inside PositionManager. This situation can arise whenever a user mints a position close to an epoch transition and provides the old epoch’s strike, or simply provides any strike that is not the exact current price at the moment of minting. From the user’s point of view the transaction appears successful – the NFT is minted and the premium is transferred – but later attempts to sell, burn, or withdraw result in a failed transaction and the user sees no balance change, often receiving a generic revert error. The impact is that funds become effectively inaccessible; the user cannot recover the premium or the notional amount tied to the position, which violates the protocol’s financial guarantees and accounting assumptions. The issue was discovered during a manual audit and reproduced with a targeted test that deliberately mismatched the strike, causing the burn call to revert. It is hard to notice because the mint operation does not emit an error and the mismatch only surfaces on subsequent operations. The proper fix is to ensure that PositionManager stores the protocol’s current strike (retrieved via IG.currentStrike()) rather than the user‑supplied value, thereby keeping the internal record consistent with the IG contract’s accounting. Aligning the stored strike with the protocol’s strike eliminates the mismatch, allowing positions to be burned or sold normally and preserving user funds.
