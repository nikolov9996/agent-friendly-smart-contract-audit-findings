---
id: 17896
severity: "High"
---

# A malicious private vault can preempt the creation of a public vault by transferring lien tokens to the public vault, thereby preventing the borrower from repaying all loans

## Description

In LienToken.transferFrom, transferring lien tokens to the public vault is prohibited because variables such as liensOpenForEpoch are not updated when the public vault receives a lien token, which would prevent the borrower from repaying the loan in that lien token.
    
```solidity
function transferFrom(
    address from,
    address to,
    uint256 id
) public override(ERC721, IERC721) {
    LienStorage storage s = _loadLienStorageSlot();
    if (_isPublicVault(s, to)) {
        revert InvalidState(InvalidStates.PUBLIC_VAULT_RECIPIENT);
    }
    if (s.lienMeta[id].atLiquidation) {
        revert InvalidState(InvalidStates.COLLATERAL_AUCTION);
    }
    delete s.lienMeta[id].payee;
    emit PayeeChanged(id, address(0));
    super.transferFrom(from, to, id);
}
```

However, public vaults are created using the ClonesWithImmutableArgs.clone function, which uses the `create` opcode, which allows the address of the public vault to be predicted before it is created.

<https://ethereum.stackexchange.com/questions/760/how-is-the-address-of-an-ethereum-contract-computed>
    
```solidity
assembly {
    instance := create(0, ptr, creationSize)
}
```

This allows a malicious private vault to transfer lien tokens to the predicted public vault address in advance, and then call AstariaRouter.newPublicVault to create the public vault, which has a liensOpenForEpoch of 0.  
When the borrower repays the loan via LienToken.makePayment, decreaseEpochLienCount fails due to overflow in _payment, resulting in the liquidation of the borrower’s collateral
    
```solidity
} else {
    amount = stack.point.amount;
    if (isPublicVault) {
        // since the openLiens count is only positive when there are liens that haven't been paid off
        // that should be liquidated, this lien should not be counted anymore
        IPublicVault(lienOwner).decreaseEpochLienCount(
            IPublicVault(lienOwner).getLienEpoch(end)
        );
    }
}
```

Consider the following scenario where private vault A provides a loan of 1 ETH to the borrower, who deposits NFT worth 2 ETH and borrows 1 ETH.  
Private Vault A creates Public Vault B using the account alice and predicts the address of Public Vault B before it is created and transfers the lien tokens to it.  
The borrower calls LienToken.makePayment to repay the loan, but fails due to overflow.  
The borrower is unable to repay the loan, and when the loan expires, the NFTs used as collateral are auctioned.

## Proof of Concept

<https://ethereum.stackexchange.com/questions/760/how-is-the-address-of-an-ethereum-contract-computed>

## Recommendation

In LienToken.transferFrom, require to.code.length >0, thus preventing the transfer of lien tokens to uncreated public vaults
    
```solidity
function transferFrom(
    address from,
    address to,
    uint256 id
) public override(ERC721, IERC721) {
    LienStorage storage s = _loadLienStorageSlot();
    if (_isPublicVault(s, to)) {
        revert InvalidState(InvalidStates.PUBLIC_VAULT_RECIPIENT);
    }
    require(to.code.length > 0);
    if (s.lienMeta[id].atLiquidation) {
        revert InvalidState(InvalidStates.COLLATERAL_AUCTION);
    }
    delete s.lienMeta[id].payee;
    emit PayeeChanged(id, address(0));
    super.transferFrom(from, to, id);
}
```

The mitigation seems like it now blocks transfers to eoas.

Indeed the mitigation may have unintended consequences.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a pre‑emptive transfer of lien tokens from a malicious private vault to the address of a public vault before the public vault contract is actually deployed. The transferFrom function in the LienToken contract is designed to reject transfers to an existing public vault, but it only checks the recipient against a stored list of known vaults and does not verify that the address already contains contract code. Because the Ethereum CREATE opcode generates contract addresses deterministically, an attacker can compute the future address of the public vault, send the lien token to that empty address, and later invoke the router to create the public vault at the predicted address. When the public vault finally exists, its internal counter for open liens (liensOpenForEpoch) is still zero, so when the borrower later calls makePayment the decreaseEpochLienCount call underflows, causing an arithmetic overflow that aborts the repayment logic and triggers liquidation of the collateral. This chain of events prevents the borrower from repaying the loan, leading to the automatic auction of the NFT used as collateral and a loss of funds for the borrower and the lending protocol. The issue occurs only when a private vault can predict the public vault address and is able to transfer lien tokens before the vault contract is created, affecting borrowers, lenders, and the overall protocol integrity. It was discovered during a security audit that examined the logical flow of lien token transfers and identified that the transferFrom guard does not consider future contract creation. The bug is subtle because the transfer succeeds without error, and the failure only manifests later during repayment, making it difficult to detect from normal transaction logs. The root cause is the reliance on a runtime check of the recipient’s vault status without confirming that the recipient is an already‑deployed contract, allowing a class of “pre‑deployment address hijacking” attacks. To remediate, the transfer function should require that the destination address contains bytecode (e.g., to.code.length > 0) or otherwise enforce that lien tokens can only be sent to existing, verified vault contracts, thereby preventing the pre‑emptive transfer and the subsequent underflow condition.
