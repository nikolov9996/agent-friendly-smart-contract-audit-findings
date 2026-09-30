---
id: 20753
severity: "High"
---

# Holders array can be manipulated by transferring or burning with amount 0, stealing rewards or bricking certain functions

## Description

`LiquidInfrastructureERC20._beforeTokenTransfer()` checks if the `to` address has a balance of `0`, and if so, adds the address to the holders array.

[LiquidInfrastructureERC20#L142-145](https://github.com/code-423n4/2024-02-althea-liquid-infrastructure/blob/main/liquid-infrastructure/contracts/LiquidInfrastructureERC20.sol#L142-L145)
```solidity
bool exists = (this.balanceOf(to) != 0);
if (!exists) {
    holders.push(to);
}
```

However, the ERC20 contract allows for transferring and burning with `amount = 0`, enabling users to manipulate the holders array.

An approved user that has yet to receive tokens can initiate a transfer from another address to themself with an amount of `0`. This enables them to add their address to the holders array multiple times. Then, `LiquidInfrastructureERC20.distribute()` will loop through the user multiple times and give the user more rewards than it should.
```solidity
for (i = nextDistributionRecipient; i < limit; i++) {
    address recipient = holders[i];
    if (isApprovedHolder(recipient)) {
        uint256[] memory receipts = new uint256[](
            distributableERC20s.length
        );
        for (uint j = 0; j < distributableERC20s.length; j++) {
            IERC20 toDistribute = IERC20(distributableERC20s[j]);
            uint256 entitlement = erc20EntitlementPerUnit[j] *
                this.balanceOf(recipient);
            if (toDistribute.transfer(recipient, entitlement)) {
                receipts[j] = entitlement;
            }
        }

        emit Distribution(recipient, distributableERC20s, receipts);
    }
}
```

This also enables any user to call burn with an amount of `0`, which will push the zero address to the holders array causing it to become very large and prevent `LiquidInfrastructureERC20.distributeToAllHolders()` from executing.

## Proof of Concept

```solidity
it("malicious user can add himself to holders array multiple times and steal rewards", async function () {
    const { infraERC20, erc20Owner, nftAccount1, holder1, holder2 } = await liquidErc20Fixture();
    const nft = await deployLiquidNFT(nftAccount1);
    const erc20 = await deployERC20A(erc20Owner);

    await nft.setThresholds([await erc20.getAddress()], [parseEther('100')]);
    await nft.transferFrom(nftAccount1.address, await infraERC20.getAddress(), await nft.AccountId());
    await infraERC20.addManagedNFT(await nft.getAddress());
    await infraERC20.setDistributableERC20s([await erc20.getAddress()]);

    const OTHER_ADDRESS = '0x1111111111111111111111111111111111111111'

    await infraERC20.approveHolder(holder1.address);
    await infraERC20.approveHolder(holder2.address);

    // Malicious user transfers 0 to himself to add himself to the holders array
    await infraERC20.transferFrom(OTHER_ADDRESS, holder1.address, 0);

    // Setup balances
    await infraERC20.mint(holder1.address, parseEther('1'));
    await infraERC20.mint(holder2.address, parseEther('1'));
    await erc20.mint(await nft.getAddress(), parseEther('2'));
    await infraERC20.withdrawFromAllManagedNFTs();

    // Distribute to all holders fails because holder1 is in the holders array twice
    // Calling distribute with 2 sends all funds to holder1
    await mine(500);
    await expect(infraERC20.distributeToAllHolders()).to.be.reverted;
    await expect(() => infraERC20.distribute(2))
        .to.changeTokenBalances(erc20, [holder1, holder2], [parseEther('2'), parseEther('0')]);
    expect(await erc20.balanceOf(await infraERC20.getAddress())).to.eq(parseEther('0'));
});

it("malicious user can add zero address to holders array", async function () {
    const { infraERC20, erc20Owner, nftAccount1, holder1 } = await liquidErc20Fixture();

    for (let i = 0; i < 10; i++) {
        await infraERC20.burn(0);
    }
    // I added a getHolders view function to better see this vulnerability
    expect((await infraERC20.getHolders()).length).to.eq(10);
});
```

## Recommendation

```solidity
function _beforeTokenTransfer(
    address from,
    address to,
    uint256 amount
) internal virtual override {
    require(!LockedForDistribution, "distribution in progress");
    if (!(to == address(0))) {
        require(
            isApprovedHolder(to),
            "receiver not approved to hold the token"
        );
    }
    if (from == address(0) || to == address(0)) {
        _beforeMintOrBurn();
    }
    if (to != address(0) && balanceOf(to) == 0 && amount > 0)
        holders.push(to);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the token contract’s _beforeTokenTransfer hook, which adds a recipient address to an internal holders array whenever the recipient’s balance is zero. The check does not consider the transfer amount, and the ERC20 standard permits transfers and burns with an amount of zero. Consequently, an attacker can invoke a zero‑value transferFrom or burn(0) to insert arbitrary addresses – including their own address multiple times or the zero address – into the holders list without changing any balances. During reward distribution, the contract iterates over the holders array and calculates each recipient’s entitlement based on their current token balance. Because duplicate entries cause the same address to be processed repeatedly, the attacker receives the full reward multiple times, effectively stealing funds that should be shared with other legitimate holders. In addition, populating the array with many zero‑address entries inflates its size, leading to out‑of‑gas reverts or complete failure of the distributeToAllHolders function, which constitutes a denial‑of‑service condition. The issue manifests whenever a zero‑amount transfer or burn is executed, which can happen at any time after a holder is approved. All token holders and the protocol’s reward mechanism are affected because the accounting invariant that each holder appears exactly once in the array is broken. The flaw was discovered during a security audit by inspecting the _beforeTokenTransfer implementation and confirming that zero‑value operations are allowed; a proof‑of‑concept test demonstrated duplicate entries and a reverted distribution call. The problem is subtle because zero‑value transfers do not modify balances and therefore appear harmless in normal transaction logs, making the corruption of the holders list easy to overlook. To remediate, the hook should only push a new address when the transfer amount is greater than zero, the recipient is not the zero address, and the recipient is an approved holder; additional safeguards can prevent the zero address from ever being added. This class of bug is an array‑injection or state‑corruption issue caused by improper handling of zero‑value token operations, violating the protocol’s accounting assumptions that each holder receives a single, proportional reward. From a user’s perspective the symptoms include receiving more reward tokens than expected, seeing distribution transactions revert unexpectedly, or observing that other users receive no rewards while the attacker’s balance grows disproportionately.
