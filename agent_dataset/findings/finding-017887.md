---
id: 17887
severity: "High"
---

# ERC4626Cloned deposit and mint logic differ on first deposit

## Description

The `ERC4626Cloned` contract is an implementation of the ERC4626 used for vaults. The standard contains a `deposit` function to deposit a specific amount of the underlying asset, and a `mint` function that will calculate the amount needed of the underlying token to mint a specific number of shares.

This calculation is done in `previewDeposit` and `previewMint`:

```solidity
function previewDeposit(
    uint256 assets
) public view virtual returns (uint256) {
    return convertToShares(assets);
}

function convertToShares(
    uint256 assets
) public view virtual returns (uint256) {
    uint256 supply = totalSupply(); // Saves an extra SLOAD if totalSupply is non-zero.

    return supply == 0 ? assets : assets.mulDivDown(supply, totalAssets());
}

function previewMint(uint256 shares) public view virtual returns (uint256) {
    uint256 supply = totalSupply(); // Saves an extra SLOAD if totalSupply is non-zero.

    return supply == 0 ? 10e18 : shares.mulDivUp(totalAssets(), supply);
}
```

In the case of the first deposit (i.e. when `supply == 0`), `previewDeposit` will return the same `assets` amount for the shares (this is the standard implementation), while `previewMint` will simply return `10e18`.

## Proof of Concept

```solidity
contract MockERC20 is ERC20("Mock ERC20", "MERC20", 18) {
    function mint(address account, uint256 amount) external {
        _mint(account, amount);
    }
}

contract TestERC4626 is ERC4626Cloned {
    ERC20 _asset;

    constructor() {
        _asset = new MockERC20();
    }

    function asset() public override view returns (address assetTokenAddress) {
        return address(_asset);
    }

    function minDepositAmount() public override view returns (uint256) {
        return 0;
    }

    function totalAssets() public override view returns (uint256) {
        return _asset.balanceOf(address(this));
    }

    function symbol() external override view returns (string memory) {
        return "TEST4626";
    }
    function name() external override view returns (string memory) {
        return "TestERC4626";
    }

    function decimals() external override view returns (uint8) {
        return 18;
    }
}

contract AuditTest is Test {
    function test_ERC4626Cloned_DepositMintDiscrepancy() public {
        TestERC4626 vault = new TestERC4626();
        MockERC20 token = MockERC20(vault.asset());

        // Amount we deposit
        uint256 amount = 25e18;
        // Shares we get if we deposit amount
        uint256 shares = vault.previewDeposit(amount);
        // Amount needed to mint shares
        uint256 amountNeeded = vault.previewMint(shares);

        // The following values should be equal but they not
        assertFalse(amount == amountNeeded);

        // An attacker can still mint a single share by using deposit to manipulate the pool
        token.mint(address(this), 1);
        token.approve(address(vault), type(uint256).max);
        uint256 mintedShares = vault.deposit(1, address(this));

        assertEq(mintedShares, 1);
    }
}
```

## Recommendation

The `deposit` function should also implement the same logic as the `mint` function for the case of the first depositor.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an inconsistency between the deposit and mint preview calculations in an ERC4626‑style vault when the vault has no existing shares (totalSupply == 0). The contract’s previewDeposit function returns the exact amount of assets supplied as the number of shares for the first depositor, which follows the ERC4626 reference implementation. In contrast, previewMint returns a fixed constant of 10e18 shares regardless of the asset amount when totalSupply is zero. This mismatch creates a logical error: the amount of assets required to mint a given number of shares is not aligned with the amount of shares received when depositing the same assets. The root cause is the special‑case handling in previewMint that does not mirror the handling in previewDeposit, leading to divergent conversion formulas for the initial deposit. An attacker can exploit the bug by performing a minimal deposit after the first deposit, receiving a share count that is far larger than the assets contributed, effectively minting shares at a dramatically reduced cost. In the provided proof‑of‑concept, after the vault is empty, a user deposits a single token and receives exactly one share, while the expected conversion would require a much larger asset amount to obtain that share. This manipulation dilutes the value of all subsequent shares, causing later users to receive fewer assets per share than anticipated, which can result in financial loss for honest participants and undermine the economic assumptions of the vault. The issue manifests only on the first deposit; once totalSupply becomes non‑zero, both preview functions use the same proportional formula and the discrepancy disappears, making the bug easy to overlook during routine testing. It was discovered during a formal audit by comparing the outputs of previewDeposit and previewMint for identical inputs when the supply was zero. The problem is subtle because the contract otherwise complies with the ERC4626 interface and the divergent behavior is hidden behind a single conditional branch. To remediate the issue, the deposit logic should be adjusted to use the same first‑deposit rule as the mint logic (or vice‑versa), ensuring that both preview functions compute shares and required assets consistently when totalSupply is zero. This alignment restores the intended 1:1 relationship between assets and shares for the initial deposit and prevents share dilution attacks, preserving the protocol’s accounting integrity and user expectations.
